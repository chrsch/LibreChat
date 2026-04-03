# Rechnungsbucher — Standalone LangChain Agent

A Python agent built with **LangChain / LangGraph** that processes PDF invoices from a Nextcloud folder and books them into the **Collmex** accounting system.

---

## Architecture

```
langchain/rechnungsbucher/
├── main.py                  # CLI entry point (interactive + single-shot)
├── agent.py                 # LangGraph ReAct agent + system prompt
├── config.py                # Env-var configuration loader
├── requirements.txt         # Python dependencies
├── .env.example             # Template for environment variables
├── clients/
│   ├── collmex.py           # Collmex CSV-over-HTTPS API client
│   └── nextcloud.py         # Nextcloud WebDAV client (PROPFIND/GET/PUT/MKCOL/MOVE/DELETE)
├── tools/
│   ├── collmex_tools.py     # LangChain @tool wrappers for Collmex
│   └── nextcloud_tools.py   # LangChain @tool wrappers for Nextcloud
└── utils/
    ├── csv_utils.py          # Collmex semicolon-CSV parsing
    └── formatting.py         # Date/number formatting helpers
```

### Tools implemented

#### Collmex tools

| Tool | Description |
|------|-------------|
| `collmex_get_vendors` | Fetch all vendor master data (numbers, names, preferred accounts) |
| `collmex_get_account_chart` | Fetch SKR03 chart of accounts |
| `collmex_get_vendor_account_history` | Historical expense-account usage per vendor |
| `collmex_select_account` | 5-level account selection logic (history → preferred → AI → static → default) |
| `collmex_upload_invoice` | Upload supplier invoices as CMXLRN records |
| `collmex_get_booking_number` | Retrieve the Collmex booking number after upload |

#### Nextcloud tools

| Tool | Description |
|------|-------------|
| `nextcloud_list_files` | List files/folders in a directory |
| `nextcloud_download_file` | Download + extract content (PDF→text via PyMuPDF, text→raw, image→base64) |
| `nextcloud_upload_file` | Upload text or base64-encoded binary |
| `nextcloud_get_file_info` | Get single-file metadata (size, MIME, ETag) |
| `nextcloud_search_files` | Case-insensitive filename search |
| `nextcloud_create_folder` | Create directories (with `mkdir -p` support) |
| `nextcloud_rename_file` | Rename a file (same directory) |
| `nextcloud_move_file` | Move/rename a file to a different location |
| `nextcloud_delete_file` | Delete a file or folder (recursive) |

---

## Prerequisites

- **Python 3.11+**
- An LLM API key (OpenAI, Anthropic, or Azure OpenAI)
- Collmex API credentials
- Nextcloud instance with WebDAV access
- Invoice PDFs in the configured Nextcloud folder

---

## Quick Start

### 1. Create a virtual environment

```bash
cd langchain/rechnungsbucher
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Required variables:

```dotenv
# LLM
LLM_PROVIDER=openai          # openai | anthropic | azure
LLM_MODEL=gpt-4o             # or claude-sonnet-4-20250514, etc.
OPENAI_API_KEY=sk-...

# Collmex
COLLMEX_CUSTOMER_ID=12345
COLLMEX_USERNAME=api_user
COLLMEX_PASSWORD=secret

# Nextcloud
NEXTCLOUD_URL=https://cloud.example.com
NEXTCLOUD_USERNAME=user
NEXTCLOUD_PASSWORD=app-password
NEXTCLOUD_WEBDAV_PATH=/remote.php/dav/files/user
```

### 4. Run the agent

**Interactive mode** (multi-turn chat):
```bash
python main.py
```

**Single-shot mode**:
```bash
python main.py "Rechnungen buchen"
```

---

## How It Works

1. The agent scans your Nextcloud invoice folder (`Buchhaltung/Eingang`)
2. Downloads and extracts text from each unprocessed PDF
3. Matches vendor names against Collmex, determines the expense account using 5-level logic
4. Presents a summary table for your review
5. After confirmation, uploads invoices to Collmex, retrieves booking numbers
6. Renames and archives files to year-based folders

---

## Supported LLM Providers

### OpenAI (default)

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

### Anthropic

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

### Azure OpenAI

```dotenv
LLM_PROVIDER=azure
LLM_MODEL=gpt-4o
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Missing required environment variable` | Check your `.env` file has all required vars |
| Collmex auth error | Verify `COLLMEX_CUSTOMER_ID`, `COLLMEX_USERNAME`, `COLLMEX_PASSWORD` |
| Nextcloud connection error | Verify `NEXTCLOUD_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_PASSWORD` |
| PDF text extraction empty | The PDF may be image-based — OCR is not included, only text-layer PDFs are supported |
| `Unsupported LLM provider` | Set `LLM_PROVIDER` to `openai`, `anthropic`, or `azure` |
| Agent runs out of iterations | Increase `AGENT_MAX_ITERATIONS` in `.env` (default: 100) |


