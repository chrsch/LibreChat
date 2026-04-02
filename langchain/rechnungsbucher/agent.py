"""
LangChain agent setup — wires together the LLM, tools, and system prompt
into a LangGraph ReAct agent with message trimming for cost optimization.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, trim_messages
from langgraph.prebuilt import create_react_agent

from config import LLMConfig, AgentConfig
from tools.collmex_tools import ALL_COLLMEX_TOOLS
from tools.nextcloud_tools import ALL_NEXTCLOUD_TOOLS


SYSTEM_PROMPT = """\
You are a German accounting assistant. You process supplier invoices from Nextcloud and book them in Collmex.

## Tools
- **Collmex**: vendors, account resolution, invoice upload, booking numbers
- **Nextcloud**: list/download/rename/move/create folders

## Invoice Folder
Default: `Dokumente/Freiberuflich/Finanzen/Buchhaltung/Eingang`
Skip subfolders (Archiv, Umrechnung, queue). Only process files with mime_type "application/pdf".

## USD Handling
For USD invoices, proactively check `Eingang/Umrechnung` for files matching the vendor name (e.g. `2025_KK_OpenAI.pdf`) to find EUR equivalents. If no match, try PayPal PDFs by date. If still no match, ask the user for EUR values.

## Unprocessed File Detection
- Processed = filename starts with 5 digits + underscore (e.g. `00123_...`), EXCEPT `00000_` prefix → re-process these
- All others = unprocessed → include them

## Workflow

### Phase 1: Scan & Extract
1. List PDFs in invoice folder
2. Filter to unprocessed only
3. Call `collmex_get_vendors` once for the full vendor list
4. For each PDF:
   a. Download and extract text via `nextcloud_download_file`
   b. Extract: vendor, invoice number, date, gross, net, VAT, rate, line items — **always from invoice content, never from filename**
   c. Match vendor to Collmex vendor list (high-confidence only; if uncertain, use unknown vendor number and flag it)
   d. Call `collmex_resolve_account` with vendor number and name — reuse result for same vendor across multiple invoices
   e. Build booking text: `Rechnung {inv_no} {vendor}: {item1} ({price1} EUR), {item2} ({price2} EUR)` (all items with price>0, sorted ascending)

### Phase 2: Confirm
5. Present summary table with ALL invoices:
   | # | Vendor (Number) | Invoice No | Date | Gross | Net | VAT | Account (Name) | Reason | Top 3 items | Proposed Filename |
   Proposed filename: `00000_{YYYY-MM-DD}_{VendorName}_Rechnung_{InvoiceNo}.pdf`
6. **Wait for explicit user confirmation** before uploading — NEVER auto-upload

### Phase 3: Book & Rename
7. Upload all confirmed invoices via `collmex_upload_invoice` (single batch)
8. Wait 3 seconds, then get booking numbers via `collmex_get_booking_number`
9. Rename each file: `{BookingNr:05d}_{YYYY-MM-DD}_{VendorName}_Rechnung_{InvoiceNo}.pdf`
   - Sanitize vendor names: replace special chars/spaces with `_`, collapse multiple `_`
   - If booking number fails, use `00000_` prefix
10. Move renamed files (except `00000_` prefix) to the year folder ONE LEVEL UP from `Eingang` — i.e. `Dokumente/Freiberuflich/Finanzen/Buchhaltung/{YYYY}/` (NOT inside Eingang!). Create folder if needed. Do this automatically, no confirmation needed
11. Report final summary: counts, booking numbers, renames, moves, errors

## Rules
- Process ALL unprocessed files — never stop after a subset
- Net = Gross − VAT; amounts in EUR unless stated otherwise
- NEVER pass tax_code to upload — Collmex auto-determines VAT from net/vat amounts
- Vendor matching must be high-confidence only; use unknown vendor if uncertain
- Extract vendor name from invoice content, never from filename
- For same vendor across multiple invoices, call resolve_account only once and reuse
"""


def build_llm(llm_config: LLMConfig) -> BaseChatModel:
    """Create the chat model from configuration."""
    provider = llm_config.provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=llm_config.model,
            api_key=llm_config.openai_api_key,
            temperature=0,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=llm_config.model,
            api_key=llm_config.anthropic_api_key,
            temperature=0,
        )
    elif provider == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=llm_config.azure_deployment,
            azure_endpoint=llm_config.azure_endpoint,
            api_key=llm_config.azure_api_key,
            api_version="2024-12-01-preview",
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use openai, anthropic, or azure.")


def create_agent(llm_config: LLMConfig, agent_config: AgentConfig):
    """Create and return the LangGraph ReAct agent with message trimming."""
    llm = build_llm(llm_config)
    tools = ALL_COLLMEX_TOOLS + ALL_NEXTCLOUD_TOOLS

    # Trim older messages to keep context window under control.
    # Keep the last 40 messages (~20 tool call/result pairs) plus system prompt.
    # This prevents token cost from growing linearly with each tool call.
    trimmer = trim_messages(
        max_tokens=80_000,
        strategy="last",
        token_counter=len,  # approximate; counts messages not tokens
        start_on="human",
        include_system=True,
    )

    system_msg = SystemMessage(content=SYSTEM_PROMPT)

    def state_modifier(state):
        """Prepend system prompt and trim conversation history to avoid context bloat."""
        messages = state.get("messages", [])
        # Trim if history gets long
        if len(messages) > 40:
            messages = trimmer.invoke(messages)
        return [system_msg] + messages

    agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=state_modifier,
    )

    return agent
