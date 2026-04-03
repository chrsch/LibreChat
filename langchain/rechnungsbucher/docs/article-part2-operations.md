# LangChain Agent vs. LibreChat Native Agent: A Real-World Comparison for Technical Leaders

## Part 2 — Observability, Cost Control, Testing, and the Migration Path

*Continuing the series for CTOs, tech leads, and AI leads shipping AI agents to production.*

---

In [Part 1](article-part1-architecture.md) we compared the architecture, tool design, and reusable components of a LangChain/LangGraph agent versus a LibreChat native agent backed by MCP servers — built against the same invoice-processing use case.

Part 2 tackles the operational questions: How do you observe what the agent is doing? How do you optimize token spend? How do you test it? And when you've validated a prototype, how do you migrate to production?

---

## Observability: Seeing Inside the Agent

AI agents are non-deterministic. The same input can produce different tool-call sequences on different runs. Without observability, you're debugging by reading chat logs — which doesn't scale.

### LangChain: LangSmith (or LangFuse, Phoenix, etc.)

The LangChain ecosystem has first-class tracing. Our agent enables it with three environment variables:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=rechnungsbucher
```

That's it. Zero code changes. Every `agent.invoke()` call produces a trace in LangSmith containing:

- **Full message history** — every user message, AI response, tool call, and tool result
- **Token counts** — input/output tokens per LLM call, broken down by message
- **Latency** — wall-clock time per step, identifying slow tool calls
- **Tool call arguments and return values** — exactly what the LLM sent and received
- **Nested spans** — the ReAct loop iterations, message trimming, LLM inference

A typical invoice-processing session with 12 PDFs generates a trace with 60–80 spans. You can inspect exactly *why* the agent chose account 4616 for an Apple invoice, or *where* it spent 4 seconds waiting for a Collmex API response.

#### Trace-Based Optimization: A Concrete Example

In one of our early runs, LangSmith traces revealed the agent was calling `collmex_get_vendors` **once per invoice** instead of once per session. Twelve invoices = twelve vendor list fetches, each returning the same ~200 vendors. That's ~50,000 wasted input tokens per session.

The fix was a single sentence in the system prompt:

```
3. Call `collmex_get_vendors` once for the full vendor list
```

Before LangSmith, this would have been invisible. The agent produced correct results either way — it just cost 3× more.

**Other optimizations discovered via traces:**

| Issue Found in Traces | Fix | Token Impact |
|---|---|---|
| Vendor list fetched per-invoice | Prompt: "call once, reuse" | −50K tokens/session |
| Account history fetched per-invoice for same vendor | Prompt: "reuse for same vendor" | −20K tokens/session |
| Full account chart fetched but rarely used | Removed from default workflow | −15K tokens/session |
| Raw history data passed to LLM before selection | Combined into `resolve_account` tool | −8K tokens/session |
| PDF text included line-break artifacts | `clean_text()` utility in Python | −5K tokens/session |

Cumulative effect: **~60% token cost reduction** from inspecting traces over three iteration cycles. This is the strongest argument for investing in observability early.

### LibreChat: Built-in Logging + External Options

LibreChat provides conversation-level logging in its MongoDB store and container logs:

```bash
docker compose logs api | grep -i "mcp\|tool\|collmex"
```

This gives you:
- Tool call names and timing
- MCP server connection status
- Error messages from failed tool calls

What it **doesn't** give you (as of early 2026):
- Per-token breakdowns by tool call
- Nested span trees of the agent loop
- Exportable traces for offline analysis
- A/B comparisons between prompt versions

For production LibreChat deployments, you can add observability by:

1. **Logging inside MCP servers** — each handler can emit structured logs:
   ```typescript
   console.error(JSON.stringify({
     tool: 'collmex_upload_invoice',
     vendor: args.vendor_number,
     duration_ms: Date.now() - start,
   }));
   ```
   These go to LibreChat's container stderr and can be captured by your log aggregator.

2. **External tracing via OpenTelemetry** — wire OTel spans into MCP server handlers and export to Jaeger, Grafana Tempo, or Datadog.

3. **LLM proxy logging** — route LLM calls through a proxy like LiteLLM that captures token usage and latency.

None of these are as turnkey as LangSmith's `LANGSMITH_TRACING=true`. This is a real gap in the MCP/LibreChat ecosystem today.

---

## Cost Control: Token Budgets and Message Trimming

Invoice processing is token-intensive. Each PDF produces 500–3,000 tokens of extracted text. A 15-invoice session can easily hit 200K+ input tokens without management.

### LangChain: Explicit `trim_messages`

The LangGraph agent implements a state modifier that trims conversation history:

```python
trimmer = trim_messages(
    max_tokens=80_000,
    strategy="last",
    token_counter=len,  # counts messages, not tokens
    start_on="human",
    include_system=True,
)

def state_modifier(state):
    messages = state.get("messages", [])
    if len(messages) > 40:
        return {"messages": trimmer.invoke(messages)}
    return state
```

**There's a subtle design choice here worth discussing.** The `token_counter=len` uses *message count* as a proxy for token count. This means `max_tokens=80_000` is effectively "max 80,000 messages" — an unreachable limit. The real guard is `if len(messages) > 40`: once the conversation exceeds 40 messages (~20 tool-call/result pairs), the trimmer kicks in and keeps only the most recent messages.

Why not use a real tokenizer? **Speed.** Running `tiktoken` on 40+ messages with large tool results adds latency to every agent loop iteration. A message-count heuristic is O(1) and good enough when you know your tool outputs are roughly bounded.

**When this breaks:** If a single tool result is extremely large (e.g., a full vendor list or a multi-page PDF extraction), the 40-message window can still exceed the model's context window. The fix is to also truncate individual tool results — which the LangChain agent does in its tool implementations (e.g., `nextcloud_download_file` truncates text files to 8,000 characters).

### LibreChat: Platform-Managed Context

LibreChat handles context window management internally based on the selected model's token limit. The agent configuration in `librechat.yaml` sets:

```yaml
endpoints:
  agents:
    recursionLimit: 500
    maxRecursionLimit: 500
```

This limits the total number of agent loop iterations, not tokens. The platform truncates or summarizes conversation history when approaching the model's context limit — but the strategy is less visible and configurable than the explicit LangChain approach.

**The practical result:** The LibreChat agent tends to use more tokens per session because the platform's trimming is less aggressive and less workflow-aware. The LangChain agent's 40-message window is tuned for the invoice workflow specifically.

### Cost Comparison (Approximate)

Based on processing 12 invoices with GPT-4o:

| Metric | LangChain Agent | LibreChat Native |
|--------|----------------|-----------------|
| Tool calls | ~45 | ~55 (decomposed tools) |
| Input tokens | ~80K | ~120K |
| Output tokens | ~15K | ~20K |
| Estimated cost (GPT-4o) | ~$0.30 | ~$0.50 |
| Estimated cost (Claude Sonnet) | ~$0.35 | ~$0.55 |

The ~40% cost difference comes from: (a) decomposed tools requiring more LLM reasoning turns, (b) more tool surface area increasing prompt token overhead, and (c) less aggressive context trimming.

For a 12-invoice weekly workflow, this is negligible (~$10/month difference). At scale — hundreds of users processing invoices daily — it compounds.

---

## Error Handling: Graceful Degradation for Non-Deterministic Systems

Tool failures in AI agents are unique: the LLM often *can recover on its own* if it sees the error. Both implementations lean into this.

### LangChain: Error Strings as Tool Output

```python
@tool
def collmex_upload_invoice(invoices: list[dict]) -> str:
    try:
        ...
        return json.dumps({"success": True, "records_uploaded": len(invoices)})
    except Exception as exc:
        return f"Error uploading invoices: {exc}"
```

Errors are returned as regular tool output, not raised as exceptions. The LLM sees `"Error uploading invoices: HTTP 401 Unauthorized"` and can reason about it — perhaps retrying, asking the user for help, or skipping that step.

This pattern means the agent loop **never crashes** from a tool failure. The trade-off: errors are less structured. Monitoring requires parsing free-text error strings from traces.

### MCP: `isError` Flag

```typescript
return {
  content: [{ type: 'text', text: `Error uploading file: ${msg}` }],
  isError: true,
};
```

MCP's protocol-level `isError` flag tells the host this is an error, not a successful result. LibreChat can surface this differently in the UI (e.g., a red indicator) and aggregate error rates per tool. The error text is still an unstructured string, but the flag enables **protocol-aware error handling** that a generic platform can act on.

Both approaches handle the same fundamental insight: **let the LLM see failures and decide what to do**. The MCP approach just makes error detection automatable.

---

## Testing Strategies

### LangChain: Direct Tool Testing

LangChain tools are regular Python functions. You can test them directly:

```python
def test_resolve_account_historical():
    init_collmex_tools(mock_config)
    result = collmex_resolve_account.invoke({
        "vendor_number": "70001",
        "vendor_name": "Apple",
    })
    data = json.loads(result)
    assert data["source"] == "historical"
    assert data["account"] == "4616"
```

The module-level singleton pattern requires `init_collmex_tools()` in test setup. To mock the Collmex API, you monkey-patch `_client` or use `unittest.mock.patch`. Not elegant, but functional.

**End-to-end agent testing** is harder. You can invoke the full agent with a test prompt:

```python
result = agent.invoke({"messages": [{"role": "user", "content": "Rechnungen buchen"}]})
```

But the result depends on the LLM's non-deterministic behavior. LangSmith provides **dataset evaluation** — you define input/expected-output pairs and run them through the agent, measuring accuracy, tool-call patterns, and cost. This is the gold standard for agent evaluation.

### MCP: Handler Unit Testing

MCP tool handlers are pure async functions with explicit dependencies:

```typescript
// Testable in isolation — no global state
const result = await handleUploadInvoice(mockClient, {
  invoices: [{ vendor_number: '70001', ... }],
});
expect(result.content[0].text).toContain('"success": true');
```

No singleton initialization needed. Pass a mock client, get structured output. This is **cleaner for unit testing** than the LangChain pattern.

**Integration testing** can use the MCP SDK's test utilities to spin up a server in-memory:

```typescript
const server = createMcpServer(mockConfig);
const result = await server.callTool('collmex_get_vendors', {});
```

**End-to-end testing** in LibreChat is less mature. You'd need to either automate the UI or use the LibreChat API to send messages to an agent and validate responses — which is more infrastructure than most teams set up.

---

## The Migration Path: Prototype to Production

Many teams will prototype in LangChain and deploy via LibreChat. Here's the practical path:

### Step 1: Prototype the Tools in LangChain

Build your tools as `@tool` functions with embedded API clients. Use LangSmith to iterate on the prompt and tool design. Don't worry about protocol compliance or decomposition — optimize for speed of iteration.

### Step 2: Stabilize Tool Interfaces

Once the tool inputs/outputs are stable, freeze the interface. The `args_schema` Pydantic models from LangChain map 1:1 to Zod schemas for MCP:

| LangChain (Pydantic) | MCP (Zod) |
|---|---|
| `str = Field(description="...")` | `z.string().describe("...")` |
| `Optional[str] = Field(default=None)` | `z.string().nullish()` |
| `int = Field(default=2)` | `z.number().default(2)` |
| `list[dict]` | `z.array(z.object({...}))` |

### Step 3: Extract API Clients

Pull your API clients (Collmex, Nextcloud, etc.) out of the tool files into standalone modules. These should have no LangChain dependencies. In our case, `clients/collmex.py` became `collmex-client.ts` — same API structure, different language.

### Step 4: Build MCP Server Wrappers

Create a new MCP server per API domain. Each tool handler delegates to the extracted client:

```typescript
server.tool('collmex_get_vendors', description, schema,
  async () => handleGetVendors(client, config)
);
```

Consider whether to keep combined tools (like `resolve_account`) or decompose them. Decomposition is better for multi-agent reuse; combination is better for token efficiency.

### Step 5: Port the System Prompt

The LangChain system prompt needs to be **expanded** for the MCP context:

- Add instructions for any decomposed tools the LLM now calls separately
- Add references to MCP tool names (they may differ from LangChain names)
- Add any rules that were implicit in combined tool logic and now need to be explicit in the prompt

In our case: 53-line prompt → 160-line prompt, mostly because `resolve_account` was decomposed into `get_history` + `select_account`.

### Step 6: Validate with Parallel Runs

Run both agents against the same set of invoices. Compare:

- **Correctness**: Same accounts selected? Same booking numbers?
- **Cost**: Token usage per session
- **Reliability**: Error recovery, edge case handling
- **Speed**: End-to-end time for a batch

Keep the LangChain agent around as a regression baseline and batch-processing fallback.

---

## Decision Framework

| Question | If Yes → | If No → |
|---|---|---|
| Do you need a web UI for non-technical users? | LibreChat + MCP | LangChain CLI |
| Will multiple agents share these tools? | MCP servers | LangChain tools |
| Is LangSmith-grade observability critical? | LangChain (for now) | Either works |
| Is your team Python-first? | LangChain | MCP (TypeScript) |
| Do you need sub-$0.50/session costs? | LangChain (combined tools) | Either works |
| Are you already running LibreChat? | Add MCP servers | LangChain standalone |
| Is this a batch/cron automation? | LangChain | — |
| Do you need Claude Desktop / Cursor compatibility? | MCP servers | LangChain |

---

## Key Takeaways

1. **LangChain agents are faster to prototype**, with less boilerplate and immediate access to LangSmith tracing. They're ideal for single-purpose automations owned by developers.

2. **MCP servers are more reusable** across hosts, agents, and even languages. They're the better investment if you're building a tool platform, not just one agent.

3. **Observability is the biggest gap** in the MCP/LibreChat ecosystem today. If you need trace-level insight into agent behavior, LangSmith is materially ahead.

4. **Combined tools reduce cost; decomposed tools increase flexibility.** The right choice depends on whether you're optimizing for one workflow or many.

5. **The migration path is well-defined.** Prototype in LangChain with LangSmith, extract API clients, build MCP wrappers, expand the prompt. Budget for the prompt to grow 2–3× when decomposing tools.

6. **Both approaches solved the same problem successfully.** The real question isn't "which is better" but "what are you optimizing for" — iteration speed, multi-user access, tool reuse, observability, or cost.

---

*This concludes the two-part series. Both the LangChain agent and the MCP servers are part of the [Rechnungsbücher project](https://github.com/) — an open-source invoice-processing agent for Collmex and Nextcloud.*

*Questions or war stories about shipping AI agents to production? Connect on [LinkedIn].*
