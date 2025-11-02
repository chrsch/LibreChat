# Model Configuration for LibreChat

This document explains how to configure the invoice extraction model in LibreChat.

## Model Details

**Model Name**: `qwen2.5-3b-instruct-invoice-extractor-gtx1650`

**Base Model**: `qwen2.5:3b-instruct`

**Optimization**: GTX 1650 (4GB VRAM)

**Context Window**: 4096 tokens

**Temperature**: 0.15 (low for deterministic JSON output)

## Configuration Steps

### 1. Add Model to .env

Edit `.env` in the LibreChat root directory:

```bash
# Add the invoice extraction model to OLLAMA_MODELS
OLLAMA_MODELS=llama3.2-3b-local:Modelfiles/llama3.2-3b-gtx1650/Modelfile,llama3.2-3b-rag:Modelfiles/llama3.2-3b-RAG-gtx1650/Modelfile,qwen2.5-3b-instruct-invoice-extractor-gtx1650:Modelfiles/qwen2.5-3b-instruct-invoice-extractor-gtx1650/Modelfile
```

### 2. Configure LibreChat to Use Ollama

Edit `librechat.yaml`:

```yaml
endpoints:
  custom:
    - name: "Ollama"
      apiKey: "ollama"
      baseURL: "http://ollama:11434/"
      models:
        fetch: true # Automatically fetches all models including invoice extractor
```

**Note**: The `default` array in `models` is optional when `fetch: true` is enabled. LibreChat will automatically discover all models created in Ollama, including the invoice extractor model.

### 3. Restart Ollama Container

After updating `.env`, restart the Ollama container:

```bash
docker compose up -d --force-recreate ollama
```

The init script will automatically:
- Pull the base `qwen2.5:3b-instruct` model if needed
- Create the custom model from the Modelfile
- Warm up the model
- Make it available to LibreChat

### 4. Verify Model is Available

Check that the model was created:

```bash
docker exec -it Ollama ollama list
```

You should see `qwen2.5-3b-instruct-invoice-extractor-gtx1650:latest` in the list.

## Model Parameters

The invoice extraction model uses these optimized parameters (defined in the Modelfile):

```
FROM qwen2.5:3b-instruct

# Context and batch settings
PARAMETER num_ctx 4096        # 4K context window for invoice documents
PARAMETER num_batch 512       # Batch size optimized for GTX 1650
PARAMETER num_keep 256        # Keep tokens in memory

# Low temperature for deterministic output
PARAMETER temperature 0.15    # Very low for consistent JSON extraction
PARAMETER top_p 0.9
PARAMETER top_k 40

# Reduce repetition in structured output
PARAMETER repeat_last_n 64
PARAMETER repeat_penalty 1.05

# Stop tokens
PARAMETER stop "<|endoftext|>"
PARAMETER stop "<|im_end|>"

SYSTEM """You are a precise invoice data extraction assistant..."""
```

## Usage in LibreChat

### Via UI

1. Open LibreChat
2. Create a new conversation or agent
3. Select **Ollama** as the endpoint
4. Choose **qwen2.5-3b-instruct-invoice-extractor-gtx1650** from the model dropdown
5. Upload your invoice PDF using "Upload as Text"
6. Use the extraction prompt from [`docs/prompt-template.md`](docs/prompt-template.md)

### Via API

See the main [README.md](README.md) for Python API usage examples.

## Performance Optimization

To find optimal settings for your hardware:

```bash
cd /path/to/LibreChat
MODEL=qwen2.5-3b-instruct-invoice-extractor-gtx1650 CTX=4096 ./ollama/optimize.sh
```

This will test different GPU layer and batch size combinations and recommend the best settings.

## Troubleshooting

### Model Not Appearing in UI

1. Check Ollama logs:
   ```bash
   docker logs Ollama | tail -50
   ```

2. Verify model exists:
   ```bash
   docker exec -it Ollama ollama list
   ```

3. Check LibreChat can reach Ollama:
   ```bash
   docker exec -it LibreChat curl http://ollama:11434/api/tags
   ```

### Model Creation Failed

If the init script fails to create the model:

```bash
# Enter Ollama container
docker exec -it Ollama bash

# Manually create the model
cd /root/.ollama
ollama create qwen2.5-3b-instruct-invoice-extractor-gtx1650 \
  -f Modelfiles/qwen2.5-3b-instruct-invoice-extractor-gtx1650/Modelfile

# Test the model
ollama run qwen2.5-3b-instruct-invoice-extractor-gtx1650 "Hello"
```

### Model Too Slow

1. Run the optimization script (see above)
2. Apply recommended `gpu_layers` and `num_batch` to the Modelfile
3. Restart Ollama to apply changes

### Out of Memory

If you get OOM errors:

1. Reduce `num_ctx` from 4096 to 3072 or 2048
2. Reduce `num_batch` from 512 to 256
3. Update the Modelfile and recreate the model

## Related Documentation

- [Main Ollama Setup](../../README-Ollama-Extension.md) - General Ollama configuration
- [Invoice Extraction Guide](docs/quickstart.md) - Using the model
- [Python API](docs/api-reference.md) - Programmatic usage
