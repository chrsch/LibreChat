# SearXNG Web Search Extension for LibreChat

## Overview
SearXNG has been integrated into your LibreChat stack as a self-hosted, privacy-focused meta search engine. This eliminates the need for third-party search API keys like Serper.

## What's Been Configured

### 1. Docker Services
- **SearXNG container** added to `docker-compose.override.yml`
  - Runs on port 8080 (internal to Docker network)
  - Accessible at http://localhost:8080 from host
  - Configuration stored in `./searxng/settings.yml`
  - No authentication required for internal network access

### 2. Ollama Service
- **Ollama container** with automated model initialization
  - Runs on host network at http://host.docker.internal:11434/
  - Auto-pulls and creates `llama3.2-3b-local` model on startup
  - Optimized Modelfile for GTX 1650 (4GB VRAM):
    - Context window: 512 tokens
    - Batch size: 160
    - GPU layers: 27
  - Located in `./ollama/` directory with init script

### 3. LibreChat Configuration
- **librechat.yaml** updated with:
  - Web search interface enabled
  - SearXNG as search provider
  - Firecrawl as scraper (API key required)
  - Jina as reranker (API key required)
  - Custom Ollama endpoint with `tools` capability
  - Optimized model parameters for small GPU

### 4. Environment Variables
Environment variables are configured in both `.env` and `docker-compose.override.yml`:
- `SEARXNG_INSTANCE_URL=http://searxng:8080`
- `FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}`
- `JINA_API_KEY=${JINA_API_KEY}`

**Important**: When using `docker-compose.override.yml` with an `environment:` section, you must explicitly pass environment variables using `${VAR_NAME}` syntax. They are not automatically inherited from the `.env` file.

## Required: API Keys

You need API keys for the scraper and reranker services:

### 1. Firecrawl (Web Scraping)
- **Free tier available**: 500 credits/month
- Sign up at: https://firecrawl.dev
- Get your API key from the dashboard
- Add to `.env` file:
  ```bash
  FIRECRAWL_API_KEY=fc-your-api-key-here
  ```

### 2. Jina (Reranking)
- **Free tier available**: 1M tokens/month
- Sign up at: https://jina.ai/api-dashboard/
- Get your API key
- Add to `.env` file:
  ```bash
  JINA_API_KEY=jina_your-api-key-here
  ```

**Alternative**: Instead of Jina, you can use Cohere for reranking:
- Sign up at: https://dashboard.cohere.com/
- Set `COHERE_API_KEY` in `.env`
- Update `librechat.yaml` to use `rerankerType: "cohere"`

### 3. Environment Variables Must Be Passed to Container
In `docker-compose.override.yml`, ensure the API keys are explicitly passed:
```yaml
services:
  api:
    environment:
      - NODE_ENV=development
      - SEARXNG_INSTANCE_URL=http://searxng:8080
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
      - JINA_API_KEY=${JINA_API_KEY}
```

After adding keys, recreate the LibreChat container:
```bash
docker compose up -d api
```

Verify keys are loaded:
```bash
docker exec LibreChat env | grep -E "FIRECRAWL|JINA"
```

## Starting the Services

1. **Start all containers**:
   ```bash
   docker compose down
   docker compose up -d
   ```

2. **Verify all services are running**:
   ```bash
   docker ps
   ```
   You should see: LibreChat, mongodb, meilisearch, rag_api, vectordb, searxng, ollama

3. **Check Ollama model initialization**:
   ```bash
   docker logs ollama
   ```
   Should show "llama3.2-3b-local model is ready!"

4. **Test SearXNG directly**:
   Open http://localhost:8080 in your browser

5. **Check LibreChat logs**:
   ```bash
   docker logs LibreChat --tail 50
   ```

## Using Web Search in LibreChat

### Current Status: ⚠️ Experimental with Ollama

**Important Note**: As of LibreChat v0.8.0, **Ollama is NOT an officially supported provider for web search functionality**. The Agents endpoint (which powers web search) officially supports:
- OpenAI
- Azure OpenAI
- Google (Gemini)
- Anthropic (Claude)
- AWS Bedrock

### What Works
- ✅ Tools menu is visible in the UI
- ✅ Web search toggle appears
- ✅ SearXNG, Firecrawl, and Jina are properly configured
- ✅ Environment variables are loaded correctly
- ✅ All backend services are running

### What Doesn't Work Yet
- ❌ Web search with `llama3.2-3b-local` fails with "Operation aborted" errors
- ❌ No tool execution logs appear (tool calling may not be triggering)
- ❌ Small models like llama3.2-3b may not support tool calling properly

### Recommendations for Testing
To test if the web search setup is working, try using a more capable model:

1. **Test with a larger Ollama model** that has better tool calling support:
   ```bash
   # Pull a model known for tool calling
   docker exec ollama ollama pull qwen2.5:7b
   # or
   docker exec ollama ollama pull mixtral:8x7b
   ```

2. **Or use a supported provider** (recommended for production):
   - Add OpenAI API key and test with GPT-4
   - Add Anthropic API key and test with Claude
   - Add Google API key and test with Gemini

### How to Enable (Experimental)
1. Open LibreChat at http://localhost:3080
2. Select the "Ollama" endpoint
3. Choose "llama3.2-3b-local" model (or larger model)
4. Click the **tools dropdown** (🔧) in the chat input bar
5. Enable **Web Search** toggle
6. Try a search query

### Troubleshooting Web Search
If you see "Operation aborted" errors:
- This is a known limitation with small Ollama models
- Check logs: `docker logs LibreChat --follow`
- Try a larger model with better tool calling support
- Consider using a supported provider (OpenAI, Anthropic, Google)

## SearXNG Configuration

The SearXNG configuration is located at `./searxng/settings.yml`. Current settings:

- **Output format**: JSON enabled (required for LibreChat)
- **Safe search**: Moderate (level 1)
- **Enabled engines**: Google, DuckDuckGo, Bing, Brave, Wikipedia
- **Language**: English (en)
- **Autocomplete**: Google

You can customize:
- Search engines (enable/disable specific engines)
- Safe search level: 0 (OFF), 1 (MODERATE), 2 (STRICT)
- Language settings
- Result limits

After modifying `settings.yml`, restart the SearXNG container:
```bash
docker restart SearXNG
```

## Security Notes

### SearXNG Secret Key
The `secret_key` in `searxng/settings.yml` should be changed from the default. Generate a random string:
```bash
openssl rand -hex 32
```

Then update the `secret_key` value in `searxng/settings.yml` and restart the container.

### API Keys
- Never commit `.env` file to version control
- API keys are passed securely through environment variables
- Keys are only accessible within the Docker network

## Troubleshooting

### SearXNG not starting
```bash
docker logs SearXNG
# Check if port 8080 is available
sudo netstat -tulpn | grep 8080
```

### Ollama model not loading
```bash
docker logs ollama
# Manually pull model
docker exec ollama ollama pull llama3.2:3b
# Check if model exists
docker exec ollama ollama list
```

### Web search not working in LibreChat
1. Check that all containers are running: `docker ps`
2. Verify API keys are loaded in container:
   ```bash
   docker exec LibreChat env | grep -E "SEARXNG|FIRECRAWL|JINA"
   ```
3. Check LibreChat logs: `docker logs LibreChat --tail 50`
4. Test SearXNG directly at http://localhost:8080
5. Try with a larger, more capable model
6. Consider using a supported provider (OpenAI, Anthropic, Google)

### "Operation aborted" errors
This typically means:
- The model doesn't support tool calling properly
- Try a larger model (qwen2.5:7b, mixtral:8x7b)
- Or use a supported provider for web search

### Port conflicts
If port 8080 is already in use, edit `docker-compose.override.yml`:
```yaml
searxng:
  ports:
    - "8081:8080"  # Use 8081 instead
```

Then update `SEARXNG_INSTANCE_URL` in `.env` to `http://searxng:8080` (internal port stays the same).

## File Structure

```
LibreChat/
├── docker-compose.override.yml    # Added SearXNG and Ollama services
├── librechat.yaml                 # Web search and endpoint configuration
├── .env                           # Environment variables (not in git)
├── searxng/
│   └── settings.yml               # SearXNG configuration
└── ollama/
    ├── init-ollama.sh             # Auto-initialization script
    └── Modelfiles/
        └── llama3.2-3b-gtx1650/
            └── Modelfile          # Optimized model parameters
```

## Benefits of This Setup

✅ **Privacy**: Self-hosted search, no data sent to third parties  
✅ **Cost Effective**: No API fees for search provider (only scraper/reranker)  
✅ **Full Control**: Customize search engines, filters, and behavior  
✅ **Automation**: Ollama models auto-initialize on startup  
✅ **Optimized**: GPU settings tuned for GTX 1650 (4GB VRAM)  

## Known Limitations

⚠️ **Ollama Web Search**: Not officially supported in LibreChat v0.8.0
- Small models (llama3.2-3b) may not support tool calling
- Larger models may work better (qwen2.5:7b, mixtral:8x7b)
- For production use, consider supported providers

⚠️ **GPU Memory**: llama3.2-3b-local is optimized for 4GB VRAM
- Larger models require more VRAM
- Adjust `gpu_layers` in librechat.yaml if needed

## Next Steps

1. **Test with a capable model**:
   - Pull a larger Ollama model with tool calling support
   - Or add an OpenAI/Anthropic API key for testing

2. **Monitor logs during testing**:
   ```bash
   docker logs LibreChat --follow
   ```

3. **Document your findings**:
   - Which models work with web search?
   - What error messages appear?
   - Share findings with the LibreChat community

## Resources

- **SearXNG**: https://docs.searxng.org/
- **LibreChat Web Search**: https://www.librechat.ai/docs/features/web_search
- **LibreChat Agents**: https://www.librechat.ai/docs/features/agents
- **Firecrawl API**: https://docs.firecrawl.dev/
- **Jina API**: https://jina.ai/api-dashboard/
- **Ollama**: https://ollama.ai/library
- **LibreChat GitHub**: https://github.com/danny-avila/LibreChat/issues

## Contributing

If you get web search working with specific Ollama models, please:
1. Document your configuration
2. Share on the LibreChat GitHub discussions
3. Help others troubleshoot similar setups

---

**Last Updated**: November 2025  
**LibreChat Version**: v0.8.0  
**Configuration Version**: 1.2.8
