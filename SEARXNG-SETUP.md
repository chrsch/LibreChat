# SearXNG Web Search Setup for LibreChat

## Overview
SearXNG has been added to your LibreChat stack as a self-hosted, privacy-focused search engine. This eliminates the need for third-party search API keys like Serper.

## What's Been Configured

### 1. Docker Services
- **SearXNG container** added to `docker-compose.override.yml`
  - Runs on port 8080
  - Accessible at http://localhost:8080
  - Configuration stored in `./searxng/settings.yml`

### 2. LibreChat Configuration
- **librechat.yaml** updated with web search settings:
  - Search Provider: SearXNG (self-hosted)
  - Scraper: Firecrawl (requires API key)
  - Reranker: Jina (requires API key)

### 3. Environment Variables
- **SEARXNG_INSTANCE_URL** set to `http://searxng:8080` in `.env`

## What You Need To Do

### Required: Get API Keys

You still need API keys for the scraper and reranker services:

#### 1. Firecrawl (Web Scraping)
- **Free tier available**: 500 credits/month
- Sign up at: https://firecrawl.dev
- Get your API key from the dashboard
- Add to `.env` file:
  ```
  FIRECRAWL_API_KEY=fc-your-api-key-here
  ```

#### 2. Jina (Reranking)
- **Free tier available**: 1M tokens/month
- Sign up at: https://jina.ai/api-dashboard/
- Get your API key
- Add to `.env` file:
  ```
  JINA_API_KEY=jina_your-api-key-here
  ```

**Alternative**: Instead of Jina, you can use Cohere for reranking:
- Sign up at: https://dashboard.cohere.com/
- Uncomment and set `COHERE_API_KEY` in `.env` instead of `JINA_API_KEY`

### Optional: Configure via UI
If you don't set the API keys in `.env`, users will be prompted to enter them via the LibreChat UI when they first use web search.

## Starting the Services

1. **Start all containers**:
   ```bash
   docker compose down
   docker compose up -d
   ```

2. **Verify SearXNG is running**:
   ```bash
   docker logs SearXNG
   ```
   
3. **Test SearXNG directly**:
   Open http://localhost:8080 in your browser

4. **Check LibreChat logs**:
   ```bash
   docker logs LibreChat
   ```

## Using Web Search in LibreChat

1. Open LibreChat at http://localhost:3080
2. Click the **tools dropdown** (🔧) in the chat input bar
3. Click the **gear icon** next to "Web Search"
4. Configure:
   - Search Provider: SearXNG
   - Instance URL: Already set (http://searxng:8080)
   - Scraper: Firecrawl
   - Reranker: Jina (or Cohere)
5. Enable **Web Search** toggle
6. Start searching!

## SearXNG Configuration

The SearXNG configuration is located at `./searxng/settings.yml`. You can customize:

- **Search engines**: Enable/disable Google, DuckDuckGo, Bing, Brave, Wikipedia, etc.
- **Safe search level**: 0 (OFF), 1 (MODERATE), 2 (STRICT)
- **Language settings**: Default is English
- **Autocomplete**: Currently set to Google

After modifying `settings.yml`, restart the SearXNG container:
```bash
docker restart SearXNG
```

## Security Note

The `secret_key` in `searxng/settings.yml` should be changed from the default. Generate a random string:
```bash
openssl rand -hex 32
```

Then update the `secret_key` value in `searxng/settings.yml` and restart the container.

## Troubleshooting

### SearXNG not starting
```bash
docker logs SearXNG
```

### Web search not working in LibreChat
1. Check that all containers are running: `docker ps`
2. Verify API keys are set correctly in `.env`
3. Check LibreChat logs: `docker logs LibreChat`
4. Test SearXNG directly at http://localhost:8080

### Port 8080 already in use
Edit `docker-compose.override.yml` and change the port mapping:
```yaml
ports:
  - "8081:8080"  # Use 8081 instead
```

Then update `SEARXNG_INSTANCE_URL` in `.env` to match the new port.

## Benefits of This Setup

✅ **Privacy**: Self-hosted, no data sent to third parties for search  
✅ **Cost**: No API fees for search provider (only scraper/reranker)  
✅ **Control**: Full control over search engines and settings  
✅ **Flexibility**: Can customize search engines, filters, and behavior  

## Resources

- SearXNG Documentation: https://docs.searxng.org/
- LibreChat Web Search Docs: https://www.librechat.ai/docs/features/web_search
- Firecrawl API Docs: https://docs.firecrawl.dev/
- Jina API Docs: https://jina.ai/api-dashboard/
