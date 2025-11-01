#!/bin/bash
set -e

# Read configuration from environment variables with defaults
MODEL_NAME="${OLLAMA_MODEL_NAME:-llama3.2-3b-local:latest}"
MODELFILE_PATH="${OLLAMA_MODELFILE_PATH:-Modelfiles/llama3.2-3b-gtx1650/Modelfile}"

echo "Starting Ollama service..."
echo "Configuration: Model='${MODEL_NAME}', Modelfile='/root/.ollama/${MODELFILE_PATH}'"

# Start Ollama in the background
/bin/ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama to be ready..."
# Wait for Ollama to be ready (max 60 seconds)
for i in {1..60}; do
    if ollama list >/dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "Timeout waiting for Ollama to start"
        exit 1
    fi
    sleep 1
done

echo "Checking if ${MODEL_NAME} model exists..."
if ollama list | grep -q "${MODEL_NAME}"; then
    echo "Model ${MODEL_NAME} already exists, skipping creation."
else
    echo "Creating ${MODEL_NAME} model..."
    # Create the model from the Modelfile
    if ollama create "${MODEL_NAME}" -f "/root/.ollama/${MODELFILE_PATH}"; then
        echo "Model ${MODEL_NAME} created successfully!"
    else
        echo "Failed to create model ${MODEL_NAME}"
        exit 1
    fi
fi

echo "Verifying model is ready to use..."
# Test that the model can actually be loaded (this ensures Ollama is truly ready)
for i in {1..30}; do
    if ollama show "${MODEL_NAME}" >/dev/null 2>&1; then
        echo "Model ${MODEL_NAME} is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Timeout waiting for model to be ready"
        exit 1
    fi
    echo "Waiting for model to be fully loaded..."
    sleep 2
done

echo "Warming up model ${MODEL_NAME}..."
# Send a simple prompt to preload the model into memory
if echo "Hello" | ollama run "${MODEL_NAME}" >/dev/null 2>&1; then
    echo "Model warm-up complete!"
else
    echo "Warning: Model warm-up failed, but continuing anyway..."
fi

echo "Ollama initialization complete. Model ready."

# Keep the Ollama process running
wait $OLLAMA_PID
