# Extension to provide Ollama

- Added support for Ollama with custom models inkl. optimize script.

## Coosing the model to be used by Ollama

List available models ```docker exec -it Ollama ollama list```

Run a given model ```docker exec -it Ollama ollama run llama3.2-3b-local```

You can find available models here: https://ollama.com/library?sort=newest

### Using Ollama container bash

In general you choose a model and run it with ```ollama run <model-name>```

Enter bash of Ollama container ```docker exec -it Ollama bash```

Run a given model ```ollama run llama3.2-3b-local```

Delete a given model ```ollama rm llama3.2-3b-local```

### Create a model with a Modelfile

Modelfile
```
FROM llama3.2:3b

PARAMETER num_ctx 512
PARAMETER num_batch 160
PARAMETER temperature 0.2
PARAMETER repeat_penalty 1.15

PARAMETER stop "<|eot_id|>"
PARAMETER stop "<|end_of_text|>"
PARAMETER stop "User:"
PARAMETER stop "<|user|>"
PARAMETER stop "<|assistant|>"

PARAMETER num_keep 160
```

Crate model from Modelfile ```ollama create phi3-mini-local -f /root/.ollama/Modelfiles/phi3mini-gtx1650/Modelfile```

## Debugging GPU usage

Check usage of GPU ```watch -n 0.5 'docker exec Ollama nvidia-smi'```

Show CPU/GPU percentage used ```docker exec -it Ollama ollama ps```

Check logs to see if layers are actually offloaded to GPU ```docker logs -f Ollama | grep "cuda\|offload"```

## Optimizing Ollama Model Performance

The `ollama/optimize.sh` script automatically finds optimal GPU and batch settings for your hardware.

### Usage

Run the optimization script:
```bash
./ollama/optimize.sh
```

Or with custom settings:
```bash
HOST=127.0.0.1 PORT=11434 MODEL=llama3.2-3b-local CTX=512 ./ollama/optimize.sh
```

### What it does

- Tests different `gpu_layers` and `num_batch` combinations
- Measures tokens per second for each configuration
- Automatically detects OOM (out of memory) conditions
- Recommends optimal settings for your GPU

### Environment Variables

- `HOST` - Ollama host (default: 127.0.0.1)
- `PORT` - Ollama port (default: 11434)
- `MODEL` - Model to optimize (default: llama3.2-3b-local)
- `CTX` - Context window size (default: 512)
- `L_START` - Starting gpu_layers value (default: 24)
- `B_START` - Starting num_batch value (default: 128)
- `B_STEP` - Batch size increment (default: 32)
- `B_MAX` - Maximum batch size to test (default: 224)

### Example Output

```
>>> Recommended settings (best measured): gpu_layers=31  num_batch=160  num_ctx=512
    Observed throughput: 45.23 toks/s
```

Apply these settings to your Modelfile for best performance.

## Helpful docker commands

Recreate a single container from a compose stack (e. g. after changeing volumes) ```docker compose up -d --force-recreate --no-deps api```