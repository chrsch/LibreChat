# Collmex-Invoices MCP Server

## 1. Overview

The `collmex-invoice-importer` is a Python CLI tool that automates the end-to-end processing of PDF invoices into the **Collmex** accounting system. After reviewing its codebase, the following core capabilities were identified:

### Collmex API Operations (via `CollmexApiClient`)

| Operation | API Call | Purpose |
|---|---|---|
| **Fetch Vendors** | `VENDOR_GET;;1` | Retrieves all vendor master data (number, name, preferred expense account) |
| **Fetch Chart of Accounts** | `ACCDOC_GET` (2-year range) | Downloads all active accounts from historical bookings |
| **Fetch Vendor Account History** | `ACCDOC_GET` (per-vendor, multi-year) | Analyses which expense accounts were used for a specific vendor historically |
| **Upload Invoices (Batch)** | `CMXLRN` records via POST | Uploads one or many supplier invoices to Collmex |
| **Get Booking Number** | `ACCDOC_GET` (by invoice number + date) | Retrieves the Collmex-assigned booking number after upload |

### AI / Extraction Operations (via `AIExtractor`)

- Extracts structured invoice data from raw PDF text using Ollama (`qwen2.5:3b-instruct`)
- Matches vendor names against the Collmex vendor list
- Suggests expense accounts based on invoice content analysis

### Account Selection Logic (via `AccountSelector`)

5-level priority cascade:
1. **Historical** — most-used account from past bookings for this vendor (~80% of cases)
2. **Vendor Preferred** — account configured in Collmex vendor master data (Field 36)
3. **AI Suggestion** — Ollama-based content classification
4. **Static Rules** — hardcoded keyword→account mapping
5. **Default** — general expenses account `4900`

### Chained Call Pattern (Critical for MCP Design)

The existing tool chains API calls in a specific dependency order:

```
1. fetch_vendors()                → vendors dict (required by everything)
2. fetch_account_chart()          → account names for display/validation
3. For each vendor:
   fetch_vendor_account_history() → historical account usage (cached 7 days)
4. AI extraction of PDF text      → Invoice object (uses vendor list for matching)
5. select_account()               → expense account (uses history + vendor prefs + AI)
6. upload_invoices_batch()        → uploads CMXLRN records
7. get_booking_number()           → retrieves assigned booking number post-upload
```

Key data dependencies:
- Steps 3–5 require vendor data from step 1
- Step 5 requires history from step 3 and extraction from step 4
- Step 7 requires vendor_number + invoice_number + invoice_date from step 6

---

## 2. MCP Server Design: "Collmex-Invoices"

### 2.1 Architecture

The MCP server will be a **standalone Node.js (TypeScript) stdio-type MCP server** that wraps the Collmex API operations as discrete, composable tools an agent can call. It does **not** replicate the AI extraction or PDF parsing — the LibreChat agent (LLM) itself will perform the "understanding" of invoice content, while the MCP server provides the Collmex data layer.

```
┌─────────────────────────────────────────────────┐
│  LibreChat Agent (LLM)                          │
│  - Reads PDF/image via OCR capability           │
│  - Understands invoice content                  │
│  - Decides which tools to call and in what order│
│  - Confirms actions with user                   │
└────────────┬────────────────────────────────────┘
             │ MCP tool calls (stdio)
┌────────────▼────────────────────────────────────┐
│  Collmex-Invoices MCP Server                    │
│  (Node.js / TypeScript)                         │
│                                                 │
│  Tools:                                         │
│   • collmex_get_vendors                         │
│   • collmex_get_account_chart                   │
│   • collmex_get_vendor_account_history          │
│   • collmex_select_account                      │
│   • collmex_upload_invoice                      │
│   • collmex_get_booking_number                  │
│                                                 │
│  Resources:                                     │
│   • collmex://vendors (cached vendor list)      │
│   • collmex://accounts (cached chart of accts)  │
└────────────┬────────────────────────────────────┘
             │ HTTPS POST (CSV-over-HTTP)
┌────────────▼────────────────────────────────────┐
│  Collmex API                                    │
│  https://www.collmex.de/c.cmx?{id},0,data_exchange │
└─────────────────────────────────────────────────┘
```

### 2.2 Why Node.js/TypeScript Instead of Python

- LibreChat's MCP integration spawns stdio processes; the official `@modelcontextprotocol/sdk` has first-class TypeScript support
- Aligns with LibreChat's Node.js ecosystem (same runtime, same package tooling)
- The Collmex API is plain CSV-over-HTTP — no Python-specific libraries needed
- Keeps the MCP server self-contained as an npm package

### 2.3 Tool Definitions

#### Tool 1: `collmex_get_vendors`

**Purpose:** Retrieve all vendor master data from Collmex.

| Parameter | Type | Required | Description |
|---|---|---|---|
| *(none)* | — | — | Fetches all vendors for the configured company |

**Returns:** Array of `{ number, name, preferred_account }` objects.

**Agent use case:** The agent calls this first to obtain the vendor list, then uses it to match vendor names extracted from an invoice.

---

#### Tool 2: `collmex_get_account_chart`

**Purpose:** Retrieve available expense accounts (SKR03).

| Parameter | Type | Required | Description |
|---|---|---|---|
| *(none)* | — | — | Fetches all accounts from historical bookings |

**Returns:** Array of `{ number, name }` objects (e.g., `{ number: "4616", name: "Werbekosten" }`).

**Agent use case:** The agent uses this for validation/display when selecting or confirming an expense account.

---

#### Tool 3: `collmex_get_vendor_account_history`

**Purpose:** Retrieve historical expense account usage for a specific vendor.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `vendor_number` | string | yes | Collmex vendor number (e.g., "70001") |
| `years_back` | number | no | Years of history to analyze (default: 2) |

**Returns:** Array of `{ account, frequency, percentage }` objects sorted by frequency descending.

**Agent use case:** After identifying the vendor, the agent calls this to determine the most likely expense account based on historical bookings.

---

#### Tool 4: `collmex_select_account`

**Purpose:** Apply the 5-level account selection logic server-side.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `vendor_number` | string | yes | Collmex vendor number |
| `vendor_name` | string | yes | Vendor name (for static rule matching) |
| `vendor_preferred_account` | string | no | Preferred account from vendor master data |
| `account_history` | array | no | Historical account entries `[{account, frequency}]` |
| `ai_suggestion` | string | no | Account suggested by LLM analysis |

**Returns:** `{ account, reason, source }` — the selected account with explanation.

**Agent use case:** The agent can delegate the selection logic to the server, or it can make its own decision. This tool encapsulates the same 5-level priority cascade the CLI uses.

---

#### Tool 5: `collmex_upload_invoice`

**Purpose:** Upload one or more supplier invoices to Collmex.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `invoices` | array | yes | Array of invoice objects (see schema below) |

**Invoice object schema:**
```json
{
  "vendor_number": "70001",
  "invoice_date": "2024-11-15",
  "invoice_number": "INV-2024-001",
  "net_amount": 100.00,
  "vat_amount": 19.00,
  "expense_account": "4616",
  "booking_text": "Rechnung INV-2024-001 Apple: MacBook Pro (2499.00 EUR)",
  "currency": "EUR"
}
```

**Returns:** `{ success, message, records_uploaded }`.

**Agent use case:** After extracting invoice data and selecting accounts (with user confirmation), the agent calls this to create the booking in Collmex.

---

#### Tool 6: `collmex_get_booking_number`

**Purpose:** Retrieve the Collmex-assigned booking number for a recently uploaded invoice.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `vendor_number` | string | yes | Vendor number |
| `invoice_number` | string | yes | Invoice number |
| `invoice_date` | string | yes | Date in YYYY-MM-DD format |

**Returns:** `{ booking_number }` or `null` if not found.

**Agent use case:** After upload, the agent calls this to obtain the booking number for confirmation/reporting. A short delay (~2s) is recommended after upload before querying.

---

### 2.4 MCP Resources (Optional, for Context Enrichment)

| Resource URI | Description |
|---|---|
| `collmex://vendors` | Cached vendor list (auto-refreshed on `collmex_get_vendors`) |
| `collmex://accounts` | Cached chart of accounts |

These allow the agent to access reference data via MCP resource reads without repeated tool calls.

---

### 2.5 Configuration

The MCP server reads credentials from environment variables passed via `librechat.yaml`:

```yaml
mcpServers:
  Collmex-Invoices:
    type: stdio
    command: node
    args:
      - /app/mcp-servers/collmex-invoices/dist/index.js
    env:
      COLLMEX_CUSTOMER_ID: "162648"
      COLLMEX_USERNAME: "${COLLMEX_USERNAME}"
      COLLMEX_PASSWORD: "${COLLMEX_PASSWORD}"
    timeout: 60000
    initTimeout: 15000
```

Required environment variables:
- `COLLMEX_CUSTOMER_ID` — Collmex customer/company ID
- `COLLMEX_USERNAME` — API username
- `COLLMEX_PASSWORD` — API password

---

### 2.6 Typical Agent Conversation Flow

```
User: "Here's an invoice from Hetzner (attaches PDF)"

Agent (internal):
  1. OCR/read the PDF content
  2. Call collmex_get_vendors → get vendor list
  3. Match "Hetzner" → vendor 70002
  4. Call collmex_get_vendor_account_history(vendor_number="70002")
     → [{account: "4640", frequency: 12, percentage: 92%}]
  5. Call collmex_get_account_chart → validate "4640" = "Internet/Hosting"
  6. Determine: account "4640" (92% historical usage)

Agent → User:
  "I extracted the following from the Hetzner invoice:
   - Invoice No: H2024-1234
   - Date: 2024-11-01
   - Amount: €49.99 (€42.01 net + €7.98 VAT)
   - Expense Account: 4640 (Internet/Hosting) — based on 92% historical usage
   
   Shall I upload this to Collmex?"

User: "Yes, go ahead"

Agent (internal):
  7. Call collmex_upload_invoice([{...}]) → success
  8. Wait 2s, call collmex_get_booking_number(...) → "00157"

Agent → User:
  "Done! Invoice H2024-1234 has been booked in Collmex.
   Booking number: 00157"
```

---

## 3. Project Structure

```
mcp-servers/
  collmex-invoices/
    .gitignore
    package.json
    tsconfig.json
    src/
      index.ts              # MCP server entry point (stdio transport)
      collmex-client.ts     # Collmex API client (CSV-over-HTTP)
      types.ts              # Shared TypeScript interfaces
      tools/
        get-vendors.ts
        get-account-chart.ts
        get-vendor-account-history.ts
        select-account.ts
        upload-invoice.ts
        get-booking-number.ts
      utils/
        csv.ts              # CSV request/response helpers
        formatting.ts       # German number/date formatting
    dist/                   # Compiled output (generated by `tsc`)
```

---

## 4. Setup & Installation

### 4.1 Prerequisites

- LibreChat running via Docker Compose (the standard setup)
- Collmex API credentials (username, password, customer ID)
- Node.js 18+ available on the host (for building the MCP server)

### 4.2 Build the MCP Server

```bash
cd mcp-servers/collmex-invoices
npm install    # or: bun install
npm run build  # or: bun run build
```

This compiles TypeScript to `dist/` and installs dependencies to `node_modules/`.
Both directories are needed at runtime inside the container.

### 4.3 Configure Environment Variables

Add your Collmex credentials to `.env` in the LibreChat root:

```dotenv
#=================================#
# Collmex MCP Server Configuration #
#=================================#

COLLMEX_CUSTOMER_ID=162648
COLLMEX_USERNAME=your_collmex_api_username
COLLMEX_PASSWORD=your_collmex_api_password
```

### 4.4 Enable the MCP Server in `librechat.yaml`

The server is already configured in `librechat.yaml`:

```yaml
mcpServers:
  Collmex-Invoices:
    type: stdio
    command: node
    args:
      - /app/mcp-servers/collmex-invoices/dist/index.js
    env:
      COLLMEX_CUSTOMER_ID: "${COLLMEX_CUSTOMER_ID}"
      COLLMEX_USERNAME: "${COLLMEX_USERNAME}"
      COLLMEX_PASSWORD: "${COLLMEX_PASSWORD}"
    timeout: 60000
    initTimeout: 15000
```

Environment variables are resolved from the `.env` file at container startup.

### 4.5 Mount into Docker Container

In `docker-compose.override.yml`, the MCP server directory is bind-mounted:

```yaml
services:
  api:
    volumes:
      # ... other volumes ...
      - type: bind
        source: ./mcp-servers/collmex-invoices
        target: /app/mcp-servers/collmex-invoices
        read_only: true
```

### 4.6 Restart LibreChat

```bash
docker compose down && docker compose up -d
```

The MCP server starts automatically as a stdio subprocess of the LibreChat API container.

---

## 5. Creating a Collmex Invoice Agent in LibreChat

### 5.1 Create the Agent

1. Open LibreChat in your browser
2. Go to **Agents** (sidebar)
3. Click **+ New Agent**
4. Configure:

| Field | Value |
|---|---|
| **Name** | Collmex Invoice Processor |
| **Model** | Any capable model (GPT-4o, Claude 3.5, etc.) |
| **Description** | Processes PDF invoices and books them in Collmex accounting system |

### 5.2 Assign MCP Tools

Under the agent's **Actions / Tools** section:

1. Enable **Actions** (MCP tools)
2. Select the **Collmex-Invoices** server — all 6 tools:
   - `collmex_get_vendors`
   - `collmex_get_account_chart`
   - `collmex_get_vendor_account_history`
   - `collmex_select_account`
   - `collmex_upload_invoice`
   - `collmex_get_booking_number`
3. Select the **Nextcloud-Webdav** server — file access tools (list, read, rename)

### 5.3 Enable Required Capabilities

Ensure these agent capabilities are enabled (in `librechat.yaml` → `endpoints.agents.capabilities`):

- **context** — for file uploads (PDF invoices)
- **tools** — for function calling
- **actions** — for MCP tools
- **ocr** — for reading PDF invoices (if available)

### 5.4 System Prompt

Use the following system prompt for the agent:

```
You are a German accounting assistant that processes supplier invoices from a Nextcloud folder and books them in Collmex.

You have access to two MCP tool sets:
- **Collmex-Invoices** — Collmex accounting API (vendors, accounts, upload, booking numbers)
- **Nextcloud-Webdav** — Nextcloud file access (list folders, read files, rename files)

## Default Invoice Folder

Unless the user specifies otherwise, scan this Nextcloud folder:
  Dokumente/Freiberuflich/Finanzen/Buchhaltung/Eingang

## Workflow

### Phase 1: Scan & Extract

1. **List PDFs** — Use Nextcloud-Webdav to list all PDF files in the invoice folder.

2. **Filter unprocessed** — Skip files that are already processed:
   - A file is "processed" if its name starts with 5 digits followed by a space (e.g., "00123 …"), EXCEPT files starting with "00000 " which should be re-processed.
   - Files without a 5-digit prefix, or with "00000 " prefix, are unprocessed and should be included.

3. **Load Collmex reference data** — Call `collmex_get_vendors` once to get the full vendor list (including the unknown vendor number). Optionally call `collmex_get_account_chart` to get account names.

4. **Process each PDF** — For every unprocessed PDF:
   a. Read/OCR the PDF content via Nextcloud-Webdav
   b. Extract: vendor name, invoice number, invoice date, gross amount, net amount, VAT amount, VAT rate, and line items
   c. Match the vendor name to a Collmex vendor number from the vendor list
   d. Call `collmex_get_vendor_account_history` for the matched vendor
   e. Call `collmex_select_account` with all available data (history, vendor preferred account, your own AI suggestion based on invoice content)
   f. Generate the booking text (see format below)

### Phase 2: Present Summary & Confirm

5. **Present a table of ALL invoices** — Show a summary table with columns:

   | # | Vendor (Number) | Invoice No | Date | Gross | Net | VAT | Account (Name) | Reason | Proposed Filename |
   |---|---|---|---|---|---|---|---|---|---|

   The "Proposed Filename" column shows what the file will be renamed to after booking (with placeholder "00000"):
   `00000 {YYYY-MM-DD} {VendorName} Rechnung {InvoiceNo}.pdf`

6. **Wait for confirmation** — NEVER upload without explicit user approval. The user may request changes to accounts or flag issues.

### Phase 3: Book & Rename

7. **Upload all confirmed invoices** — Call `collmex_upload_invoice` with all confirmed invoices in a single batch call.

8. **Wait 3 seconds** for Collmex to process the bookings.

9. **Get booking numbers** — For each uploaded invoice, call `collmex_get_booking_number`. 

10. **Rename files** — For each invoice with a booking number, use Nextcloud-Webdav to rename the PDF file. The naming convention is:

    **Format:** `{BookingNr} {YYYY-MM-DD} {VendorName} Rechnung {InvoiceNo}.pdf`

    - BookingNr is the Collmex booking number, zero-padded to 5 digits (e.g., 123 → "00123")
    - Date is the invoice date in YYYY-MM-DD format
    - VendorName is the vendor name (sanitized: no special filesystem characters)
    - InvoiceNo is the invoice number as printed on the invoice

    **Examples:**
    - `00147 2024-11-03 Apple Rechnung INV-2024-001.pdf`
    - `00148 2024-11-15 Hetzner Rechnung R20241115-001.pdf`
    - `00000 2024-12-01 JetBrains Rechnung JTB-5678.pdf` (if booking number retrieval failed)

11. **Report results** — Show a final summary:
    - How many invoices were uploaded successfully
    - Booking numbers assigned
    - Files renamed (old name → new name)
    - Any errors or invoices where booking number retrieval failed (these keep the "00000" prefix for re-processing)

## Booking Text Format
`Rechnung {invoice_number} {vendor_name}: {item1} ({price1} EUR), {item2} ({price2} EUR)`
- Include ALL line items with price > 0
- Sort items by price ascending
- Example: "Rechnung INV-001 Apple: iCloud Storage (0.99 EUR), Apple Music (10.99 EUR)"

## Important Rules
- Always present the full summary table and wait for user confirmation before uploading
- Net amount = Gross amount − VAT amount
- Amounts use EUR unless stated otherwise
- If a vendor is not found in the vendor list, use the unknown vendor number returned by `collmex_get_vendors` and warn the user — suggest they create the vendor in Collmex first
- Files starting with 5 digits + space (except "00000") are already booked — skip them
- If booking number retrieval fails for an invoice, rename with "00000" prefix so it can be re-processed later
- Sanitize vendor names in filenames: remove characters not allowed in filenames (/ \ : * ? " < > |)
```

### 5.5 Test the Agent

1. Start a conversation with the Collmex Invoice Processor agent
2. Say "Process invoices" — the agent will scan the default Nextcloud folder
3. Review the summary table the agent presents
4. Confirm to proceed, or request adjustments
5. The agent uploads, retrieves booking numbers, and renames the PDFs

---

## 6. Implementation Notes

### Collmex API Protocol
- All requests are `POST` to `https://www.collmex.de/c.cmx?{customer_id},0,data_exchange`
- Body: semicolon-delimited CSV, UTF-8 encoded
- First line: `LOGIN;{username};{password}`
- Subsequent lines: command records (e.g., `VENDOR_GET;;1`)
- Response: semicolon-delimited CSV with record-type prefixes (`CMXLIF`, `ACCDOC`, `MESSAGE`, etc.)
- See [COLLMEX-API-SPEC.md](COLLMEX-API-SPEC.md) for full protocol documentation

### Error Handling
- Collmex API errors return `MESSAGE;E;{error_text}` — parsed and returned as structured error responses
- Network failures surface as tool errors with descriptive messages
- The upload tool validates required fields before sending to avoid partial uploads

### Security
- Credentials are passed via environment variables, never exposed in tool responses
- The MCP server does not log credentials
- All communication with Collmex is over HTTPS

---

## 7. Summary

The Collmex-Invoices MCP server exposes 6 tools that give a LibreChat agent full access to the Collmex accounting API for supplier invoice management. The design mirrors the proven call chain from the existing Python tool but decomposes it into independent, composable operations that an LLM agent can orchestrate conversationally — including vendor lookup, historical account analysis, intelligent account selection, invoice upload, and booking number retrieval.

The agent replaces the Ollama-based AI extraction (since the agent *is* the LLM) and adds a human-in-the-loop confirmation step naturally through conversation, rather than through a CLI prompt.
