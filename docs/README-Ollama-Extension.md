# Extension to provide Ollama

- Added support for Ollama with custom models inkl. optimize script.

## Configuring the models to be used by Ollama

### Configuration via .env file

Multiple models can be configured in the `.env` file using a comma-separated list:

```bash
# Model configurations (comma-separated for multiple models)
# Format: MODEL_NAME:MODELFILE_PATH
OLLAMA_MODELS=llama3.2-3b-local:Modelfiles/llama3.2-3b-gtx1650/Modelfile,llama3.2-3b-rag:Modelfiles/llama3.2-3b-RAG-gtx1650/Modelfile

# Example: Add more models
# OLLAMA_MODELS=model1:Modelfiles/folder1/Modelfile,model2:Modelfiles/folder2/Modelfile
```

**Format**: `MODEL_NAME:MODELFILE_PATH` (paths are relative to `/root/.ollama` in the container)

The model names will automatically get the `:latest` tag appended if not specified.

When you change these values, restart the Ollama container:
```bash
docker compose up -d --force-recreate ollama
```

The init script will automatically:
- Create all models from their specified Modelfiles if they don't exist
- Warm up each model sequentially so they're ready for first use
- Health check will ensure all models are available before LibreChat starts

### Available Models

This setup includes example models optimized for GTX 1650 (4GB VRAM):

| Model | Context Size | Use Case | Modelfile |
|-------|--------------|----------|-----------|
| **llama3.2-3b-local** | 512 tokens | Fast chats, quick queries | `Modelfiles/llama3.2-3b-gtx1650/` |
| **llama3.2-3b-rag** | 8192 tokens | RAG, "Upload as Text", documents | `Modelfiles/llama3.2-3b-RAG-gtx1650/` |

These are example configurations. You can add your own custom models by creating Modelfiles and adding them to `OLLAMA_MODELS` in `.env`.

## Use Cases & Extensions

### Invoice Extraction Agent

For a complete invoice extraction solution with Python API, see:
**[`librechat-agent-invoice-extractor/`](librechat-agent-invoice-extractor/)**

This includes:
- Pre-configured Qwen2.5 3B model optimized for structured data extraction
- Python CLI and API for PDF processing
- Batch processing examples
- Vendor mapping and JSON output

### Manual model management

List available models ```docker exec -it Ollama ollama list```

Run a given model ```docker exec -it Ollama ollama run llama3.2-3b-local```

You can find available models here: https://ollama.com/library?sort=newest

### Using Ollama container bash

In general you choose a model and run it with ```ollama run <model-name>```

Enter bash of Ollama container ```docker exec -it Ollama bash```

Run a given model:
```ollama run llama3.2-3b-local```
```ollama run llama3.2-3b-rag```
```ollama run <your-model-name>```

Delete a given model:
```ollama rm llama3.2-3b-local```
```ollama rm <your-model-name>```

### Create a model with a Modelfile

Example Modelfile (small context for fast inference):
```
FROM llama3.2:3b

PARAMETER num_ctx 512
PARAMETER num_batch 128
PARAMETER num_keep 160
```

Example Modelfile (large context for RAG/documents):
```
FROM llama3.2:3b

PARAMETER num_ctx 8192
PARAMETER num_batch 512
PARAMETER num_keep 256
```

Example Modelfile (custom with system prompt):
```
FROM llama3.2:3b

PARAMETER num_ctx 2048
PARAMETER num_batch 256
PARAMETER temperature 0.7

SYSTEM """You are a helpful assistant."""
```

Create model from Modelfile:
```bash
ollama create my-custom-model -f /root/.ollama/Modelfiles/my-folder/Modelfile
```

To add a new model to the multi-model configuration:
1. Create a new Modelfile directory under `ollama/Modelfiles/`
2. Add your model configuration to `OLLAMA_MODELS` in `.env`:
   ```bash
   OLLAMA_MODELS=model1:Modelfiles/folder1/Modelfile,model2:Modelfiles/folder2/Modelfile,my-custom-model:Modelfiles/my-folder/Modelfile
   ```
3. Restart Ollama: `docker compose up -d --force-recreate ollama`

## Debugging GPU usage

Check usage of GPU ```watch -n 0.5 'docker exec Ollama nvidia-smi'```

Show CPU/GPU percentage used ```docker exec -it Ollama ollama ps```

Check logs to see if layers are actually offloaded to GPU ```docker logs -f Ollama | grep "cuda\|offload"```

## Optimizing Ollama Model Performance

The `ollama/optimize.sh` script automatically finds optimal GPU and batch settings for your hardware.

### Usage

Run the optimization script for a specific model:
```bash
MODEL=llama3.2-3b-local ./ollama/optimize.sh
MODEL=llama3.2-3b-rag CTX=8192 ./ollama/optimize.sh
MODEL=your-custom-model CTX=4096 ./ollama/optimize.sh
```

Or use custom settings:
```bash
HOST=127.0.0.1 PORT=11434 MODEL=my-custom-model CTX=512 ./ollama/optimize.sh
```

### What it does

- Tests different `gpu_layers` and `num_batch` combinations
- Measures tokens per second for each configuration
- Automatically detects OOM (out of memory) conditions
- Recommends optimal settings for your GPU

### Environment Variables

- `HOST` - Ollama host (default: 127.0.0.1)
- `PORT` - Ollama port (default: 11434)
- `MODEL` - Model to optimize (**required**, e.g., `llama3.2-3b-local` or `llama3.2-3b-rag`)
- `CTX` - Context window size (default: 512, use 8192 for RAG model)
- `L_START` - Starting gpu_layers value (default: 24)
- `B_START` - Starting num_batch value (default: 128)
- `B_STEP` - Batch size increment (default: 32)
- `B_MAX` - Maximum batch size to test (default: 224)

**Note:** You must specify the `MODEL` variable to optimize. Test each model separately with its corresponding context size.

### Example Output

```
>>> Recommended settings (best measured): gpu_layers=31  num_batch=160  num_ctx=512
    Observed throughput: 45.23 toks/s
```

Apply these settings to your Modelfile for best performance.

## Helpful docker commands

Recreate a single container from a compose stack (e. g. after changeing volumes) ```docker compose up -d --force-recreate --no-deps api```