# How I Cut My LangChain Agent's Cost by 54% and Latency by 64% — With Five Simple Optimizations

*A practical guide to profiling and optimizing a LangGraph ReAct agent using LangSmith traces.*

---

## The Agent

I built a LangChain-based accounting agent that processes PDF invoices from Nextcloud and books them into Collmex (a German accounting system). It uses a LangGraph ReAct agent with 15 tools — six for the Collmex API (vendor lookup, account resolution, invoice upload, booking numbers) and nine for Nextcloud WebDAV (list files, download PDFs, rename, move, create folders).

A typical invoice run looks like this:

1. List all PDFs in an inbox folder
2. Download each PDF and extract text
3. Match vendors, resolve expense accounts
4. Present a summary table for confirmation
5. Upload invoices to Collmex, retrieve booking numbers
6. Rename and archive the files

The agent runs on **Claude Haiku 4.5** (`claude-haiku-4-5-20241022`) — Anthropic's cheapest model — and processes 2–4 invoices per run.

## The Problem

After deploying the agent, I connected it to **LangSmith** for tracing. Analyzing six initial runs revealed:

| Metric | Value |
|---|---|
| Total tokens | 294,559 |
| Total cost | $0.48 |
| Total duration | 142s |
| LLM calls | 22 |
| Avg tokens per run | 49,093 |
| Avg cost per run | $0.08 |

That's a lot of tokens for processing a handful of invoices. Where were they going?

## Profiling with LangSmith

LangSmith's trace view made the bottlenecks immediately visible. I queried the API to get detailed per-call token breakdowns:

```bash
curl -s -X POST "https://eu.api.smith.langchain.com/api/v1/runs/query" \
  -H "x-api-key: $LANGSMITH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session": ["<project-id>"], "filter": "eq(is_root, true)", ...}'
```

### Finding 1: 42% Token Waste from Context Overhead

Every LLM call in a ReAct agent sends the full system prompt plus all tool schemas. My system prompt was **2,295 tokens** and the 15 tool schemas added another ~3,000 tokens. That's ~5,300 tokens of overhead on *every single call* — and with 7 LLM calls per run, that's 37,000 tokens just for repeated context.

### Finding 2: Redundant Tool Calls

The agent was making two separate calls to resolve an expense account: first `get_vendor_account_history`, then `select_account` with the history. That's two LLM round-trips where one would do.

### Finding 3: Unused Tools Inflating Schemas

Of the 15 tools, 4 were never used in the invoice workflow (`delete_file`, `upload_file`, `search_files`, `get_file_info`). Each unused tool added ~200 tokens of schema overhead to every call.

### Finding 4: Context Window Growth

Token usage grew from 5,642 on the first LLM call to 15,308 on the seventh — the conversation history was accumulating large tool outputs (full vendor lists, PDF text extractions) without any trimming.

## The Five Optimizations

### 1. Condense the System Prompt

I rewrote the system prompt from 2,295 tokens down to ~1,500 tokens. The key was eliminating redundant instructions (the original had "Process ALL Files" stated three times) and using terser formatting while preserving every behavioral rule.

**Before (excerpt):**
```
## Critical: Process ALL Files
You MUST process every single unprocessed PDF in the folder.
Never stop after a subset. If there are 20 files to process, all 20
must appear in the summary table. Do NOT skip files or stop early
for any reason.
```

**After:**
```
## Rules
- Process ALL unprocessed files — never stop after a subset
```

Same behavior, 80% fewer tokens.

### 2. Combine Redundant Tools

I merged `collmex_get_vendor_account_history` and `collmex_select_account` into a single `collmex_resolve_account` tool. One tool call now returns the recommended account directly with an explanation, eliminating an entire LLM round-trip per vendor.

```python
@tool
def collmex_resolve_account(vendor_number: int, vendor_name: str) -> str:
    """Get a vendor's booking history AND select the best expense account
    in a single call. Returns the recommended account with reasoning."""
    history = client.fetch_vendor_account_history(vendor_number)
    # Analyze history, apply rules, return recommendation
    ...
```

### 3. Remove Unused Tools

I dropped 4 tools that the invoice workflow never uses: `nextcloud_delete_file`, `nextcloud_upload_file`, `nextcloud_search_files`, and `nextcloud_get_file_info`. Also removed `collmex_get_account_chart` (rarely useful, the resolve_account tool handles this internally).

**15 tools → 9 tools** = ~1,200 fewer schema tokens per LLM call.

### 4. Compress Tool Outputs

Large tool outputs (vendor lists with 100+ entries, full PDF text extractions) were bloating the conversation history. I added output compression:

- **Vendor list**: Returns only essential fields (number, name) instead of full records
- **File listings**: Compact format with just name, size, and type
- **PDF downloads**: Returns extracted text directly without JSON wrapper overhead

### 5. Add Message Trimming

I added LangGraph's built-in message trimmer to cap conversation history growth:

```python
from langchain_core.messages import trim_messages

trimmer = trim_messages(
    max_tokens=80_000,
    strategy="last",
    token_counter=len,
    start_on="human",
    include_system=True,
)
```

This keeps only the last ~40 messages in context, preventing unbounded token growth across long multi-invoice runs.

## Results

After deploying the optimizations, I ran the same invoice-processing workflow and compared the LangSmith traces.

### All Runs (per-run averages)

| Metric | Before | After | Change |
|---|---|---|---|
| Tokens | 49,093 | 25,798 | **−47.5%** |
| Cost | $0.080 | $0.029 | **−64.2%** |
| Duration | 23.6s | 9.0s | **−61.8%** |

### Full Invoice Runs Only (>40k tokens)

| Metric | Before | After | Change |
|---|---|---|---|
| Tokens | 64,753 | 46,474 | **−28.2%** |
| Cost | $0.111 | $0.051 | **−54.2%** |
| Duration | 35.0s | 12.7s | **−63.7%** |

The cost reduction is even larger than the token reduction because one pre-optimization run accidentally used Claude Sonnet ($3/$15 per 1M tokens) instead of Haiku ($1/$5 per 1M). But even comparing Haiku-only runs, the optimizations delivered a clear 28% token reduction and 64% latency improvement.

## What Drove the Biggest Gains

The impact breakdown, roughly:

| Optimization | Token Savings | Latency Savings |
|---|---|---|
| Condensed system prompt | ~800 tok/call × 7 calls = **5,600** | Minimal |
| Removed 5 tools | ~1,000 tok/call × 7 calls = **7,000** | Minimal |
| Combined resolve_account | ~5,000 tok (one fewer round-trip) | **3–5s** |
| Compressed tool outputs | ~3,000–5,000 tok | ~1s |
| Message trimming | Prevents unbounded growth | Prevents timeouts |

The tool consolidation and schema reduction had the highest per-call impact. The system prompt compression compounds across every call. Message trimming is insurance against worst-case scenarios.

## Key Takeaways

1. **Profile first.** LangSmith traces made it obvious where tokens were going. Without data, I would have guessed wrong about the bottlenecks.

2. **System prompts are repeated on every call.** In a ReAct agent, a 2,000-token system prompt sent 7 times costs 14,000 tokens. Every word counts.

3. **Tool schemas are hidden overhead.** Each tool adds ~200 tokens of schema to every LLM call. 15 tools × 200 tokens × 7 calls = 21,000 tokens. Remove what you don't need.

4. **Combine sequential tool calls.** If the agent always calls tool A then tool B with A's output, merge them. You save an entire LLM round-trip — both the token cost and the latency.

5. **Compress tool outputs.** A full vendor list or PDF extraction can be thousands of tokens. Return only what the LLM needs.

6. **Add message trimming early.** Context windows grow linearly with tool calls. Without trimming, a 10-invoice run could hit 200k+ tokens.

## Tech Stack

- **LangChain** 0.3.x + **LangGraph** 0.3.x (ReAct agent via `create_react_agent`)
- **Claude Haiku 4.5** (`claude-haiku-4-5-20241022`) — $1/$5 per 1M tokens
- **LangSmith** for tracing, on the EU endpoint
- **Python** tools wrapping Collmex CSV API and Nextcloud WebDAV

---

*The full agent source is a standalone Python project using LangGraph's `create_react_agent` with custom tools — no MCP servers required. The optimizations described here are general and apply to any ReAct agent with multiple tools.*
