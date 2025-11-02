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

# Function to create and warm up a model
create_and_warmup_model() {
    local MODEL_NAME=$1
    local MODELFILE_PATH=$2
    
    echo "---"
    echo "Processing model: ${MODEL_NAME}"
    echo "Modelfile: /root/.ollama/${MODELFILE_PATH}"
    
    # Check if model exists
    if ollama list | grep -q "${MODEL_NAME}"; then
        echo "Model ${MODEL_NAME} already exists, skipping creation."
    else
        echo "Creating ${MODEL_NAME} model..."
        # Create the model from the Modelfile
        if ollama create "${MODEL_NAME}" -f "/root/.ollama/${MODELFILE_PATH}"; then
            echo "Model ${MODEL_NAME} created successfully!"
        else
            echo "Failed to create model ${MODEL_NAME}"
            return 1
        fi
    fi
    
    echo "Verifying model ${MODEL_NAME} is ready to use..."
    # Test that the model can actually be loaded
    for i in {1..30}; do
        if ollama show "${MODEL_NAME}" >/dev/null 2>&1; then
            echo "Model ${MODEL_NAME} is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Timeout waiting for model ${MODEL_NAME} to be ready"
            return 1
        fi
        echo "Waiting for model to be fully loaded..."
        sleep 2
    done
    
    echo "Warming up model ${MODEL_NAME}..."
    # Send a simple prompt to preload the model into memory
    if echo "Hello" | ollama run "${MODEL_NAME}" >/dev/null 2>&1; then
        echo "Model ${MODEL_NAME} warm-up complete!"
    else
        echo "Warning: Model ${MODEL_NAME} warm-up failed, but continuing anyway..."
    fi
}

# Process multiple models from OLLAMA_MODELS configuration
echo "Models to process: ${OLLAMA_MODELS}"

# Split OLLAMA_MODELS by comma and process each
IFS=',' read -ra MODEL_CONFIGS <<< "$OLLAMA_MODELS"

for config in "${MODEL_CONFIGS[@]}"; do
    # Trim whitespace
    config=$(echo "$config" | xargs)
    
    # Split by colon to get model name and modelfile path
    IFS=':' read -r MODEL_NAME MODELFILE_PATH <<< "$config"
    
    # Add :latest suffix if not present
    if [[ ! "$MODEL_NAME" =~ :.+ ]]; then
        MODEL_NAME="${MODEL_NAME}:latest"
    fi
    
    # Process this model
    create_and_warmup_model "$MODEL_NAME" "$MODELFILE_PATH" || echo "Warning: Failed to process ${MODEL_NAME}"
done

echo "---"
echo "Ollama initialization complete. All models ready."

# Keep the Ollama process running
wait $OLLAMA_PID
