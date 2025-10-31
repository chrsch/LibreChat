#!/bin/bash
set -e

echo "Starting Ollama service..."

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

echo "Checking if llama3.2-3b-local model exists..."
if ollama list | grep -q llama3.2-3b-local; then
    echo "Model llama3.2-3b-local already exists, skipping creation."
else
    echo "Creating llama3.2-3b-local model..."
    # Create the model from the Modelfile
    if ollama create llama3.2-3b-local -f /root/.ollama/Modelfiles/llama3.2-3b-gtx1650/Modelfile; then
        echo "Model llama3.2-3b-local created successfully!"
    else
        echo "Failed to create model llama3.2-3b-local"
        exit 1
    fi
fi

echo "Verifying model is ready to use..."
# Test that the model can actually be loaded (this ensures Ollama is truly ready)
for i in {1..30}; do
    if ollama show llama3.2-3b-local >/dev/null 2>&1; then
        echo "Model llama3.2-3b-local is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Timeout waiting for model to be ready"
        exit 1
    fi
    echo "Waiting for model to be fully loaded..."
    sleep 2
done

echo "Ollama initialization complete. Model ready."

# Keep the Ollama process running
wait $OLLAMA_PID
