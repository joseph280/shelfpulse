# ShelfPulse

A LangGraph-powered CPG sales-insight agent. Plain-English questions in, structured KPI snapshots, evidence-cited insights, and ranked action plans out. Built to demonstrate production-grade LLM engineering: typed I/O, structural hallucination prevention, observability, a real evaluation harness, and a Next.js chat frontend.

## 🔗 Live demo

**Try it:** https://shelfpulse-beta.vercel.app

The app is password-protected to keep API costs in check. **Email me for the password:** [joseph.feener@gmail.com](mailto:joseph.feener@gmail.com)

> _Note: the backend runs on a free tier that sleeps after ~15 min idle, so the first question may take 30–60 seconds to wake it up — subsequent ones are fast._

```mermaid
flowchart TD
    A["POST /ask"] --> B[Guardrails]
    B -->|PII / harmful / oversized| R[AskResponse Refusal]
    B -->|pass| C[Router]
    C -->|in scope| D[Planner]
    C -->|out of scope| I[Finalizer]
    D --> E[Tool Executor]
    E -->|MCP HTTP| M[("FastMCP Server<br/>7 tools<br/>DuckDB warehouse")]
    M --> E
    E --> F[Validator]
    F --> G[Insight Builder]
    G --> H[Action Planner]
    H --> I
    I --> S[(SQLite run history)]
    I --> R

    style B fill:#fff8dc,stroke:#c8a100
    style C fill:#e0f0ff,stroke:#3a7fd5
    style F fill:#ffe0e0,stroke:#c83737
    style M fill:#e8f5e9,stroke:#388e3c
    style S fill:#e8f5e9,stroke:#388e3c
```

## What is interesting about the architecture

**Evidence is materialized before the insight is written.** The validator node converts raw tool results into a typed `Evidence` list with stable IDs, and the insight builder is constrained to cite only those IDs. Hallucination of metric values becomes structurally impossible: an aggregate number cannot appear in the summary unless a real tool call produced it. The same guarantee holds in the empty-data case — see demo scenario 4.

**Tools live behind an MCP server, not inline functions.** The agent talks to FastMCP over HTTP. The same MCP server could serve a Claude desktop user or a teammate's agent without code changes. The catalog has 7 tools across products, regions, channels, sales aggregates, period comparisons, and stockout risk.

**Every LLM call is structured.** `with_structured_output(SomeModel)` at every node. Pydantic catches malformed responses at the boundary; the graph never proceeds with invalid intermediate state.

**Every request is traced.** OpenInference auto-instrumentation produces an OTEL span tree per request, viewed in Arize Phoenix. Token counts, latency, and prompts/completions visible per span.

## Quickstart

```bash
git clone <repo-url>
cd shelfpulse
uv sync
cp .env.example .env       # add your ANTHROPIC_API_KEY

# Seed the warehouse (~50k rows of synthetic CPG sales)
uv run python data/seed.py

# Terminal 1: MCP server (DuckDB + 7 tools)
uv run python -m mcp_server.server

# Terminal 2: API + agent + Phoenix
uv run uvicorn api.main:app --port 8000

# Terminal 3: try a question via curl
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Top underperforming beverage SKUs in Northeast last quarter"}'

# Or use the chat UI
cd frontend && npm install && npm run dev
# Open http://localhost:3000
```

Phoenix UI is at http://localhost:6006 once the API is up.

## Frontend

A Next.js 14 chat interface lives in `frontend/`. It calls the FastAPI `/ask` endpoint and renders responses as a chat thread.

![Chat UI — empty state](docs/frontend_empty.png)

*Empty state with three example question chips. The input is pinned at the bottom; Enter submits. The "Open Phoenix" link in the header opens the observability dashboard.*

![Chat UI — successful response](docs/frontend_response.png)

*A successful response. Insight title plus confidence at the top, narrative summary with inline `[ev-N]` citations, a collapsible evidence list, and the action plan rendered as a ranked sequence with lever badges (assortment, distribution, promo, price, planogram, supply), owner roles, and dollar-impact ranges. The trace_id at the bottom is a clickable link to Phoenix.*

![Chat UI — refusal](docs/frontend_refusal.png)

*An out-of-scope refusal. Visually distinct (yellow card) with the reason badge, the human-readable refusal message, and a trace_id link for audit. Sub-second latency since the router short-circuits without invoking the planner.*

**Frontend stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, plain `fetch` against the local FastAPI endpoint. Loading card with elapsed-seconds counter and stage-progression hints to absorb the 20-70 second agent latency. No state management library, no component library — kept lean for shipping.

## Demo scenarios

### 1. Comparison plus root cause
> *"Top underperforming beverage SKUs in Northeast last quarter vs the one before."*

Plan: one `compare_periods` at category level, two `query_sales` for per-SKU drill-down across both quarters. Insight cites three Evidence rows (Q4-2025 value, Q1-2026 value, percentage change). Action plan ranks five recommendations across `assortment`, `distribution`, `promo`, `price`, and `supply` levers.

### 2. Promo sustainability
> *"Promo lift on snacks over the last 8 weeks. Is it sustainable?"*

Plan: two `compute_kpi` calls comparing the recent 8-week window to the prior 8-week window. Returns 14 Evidence rows across both periods. The insight identifies promo-share trend and recommends reallocation across `promo` and `assortment` levers.

### 3. Out of scope refusal
> *"What's the weather in Chicago?"*

The router classifies as out of scope; the graph short-circuits to the finalizer. A structured `RefusalResponse` is returned with a fresh `trace_id` for audit. No planner, no tools, no insight LLM call. Sub-1-second latency.

### 4. Honest behavior on empty data
> *"Compare sales between Q3 2023 and Q4 2023."*

The warehouse only holds data from May 2024 forward, so these quarters are empty. The `compare_periods` tool returns zero-valued aggregates rather than failing. The validator materializes three Evidence rows showing value=0. The insight summarizes: "No sales recorded in Q3 or Q4 2023. This indicates either a data availability issue or that the business had not yet commenced operations." The action plan recommends investigating root cause (data integration, historical review, distribution audit). The structural guarantee from the validator pattern means the system cannot invent sales figures — when the data is zero, the insight says so.

## Evaluation

The eval harness in `eval/` runs 10 canned questions against the live `/ask` endpoint and grades each response against expected facts using substring and structural checks. Six in-scope analytics questions of varying complexity plus four refusal questions covering PII, prompt injection, and out-of-scope.

```bash
uv run python eval/run_eval.py
```

Latest run: **9 of 10 passed.**

| id  | result | latency | coverage |
|-----|--------|---------|----------|
| q1  | PASS   | 70.6s   | beverage period comparison with per-SKU drill |
| q2  | PASS   | 45.9s   | snack promo sustainability over 8 weeks |
| q3  | PASS   | 21.1s   | stockout risk on 30-day horizon |
| q4  | PASS   | 45.9s   | channel comparison on energy gross sales |
| q5  | FAIL   | 22.6s   | region ranking by gross margin |
| q6  | PASS   | 28.5s   | top SKUs by velocity, restock recommendation |
| q7  | PASS   | 2.6s    | out_of_scope refusal (weather) |
| q8  | PASS   | 0.0s    | pii guardrail (credit card) |
| q9  | PASS   | 0.0s    | harmful guardrail (prompt injection) |
| q10 | PASS   | 2.7s    | out_of_scope refusal (joke) |

q5 asks for the region with the highest gross margin on beverages in Q1 2026. To answer rigorously, the planner needs to fan out one `compute_kpi` call per region (12 calls), then compare. The current planner picks a single aggregate call instead, so the validator has nothing per-region to materialize as `Evidence` and the eval flags the empty list. The insight body itself is well-formed and probably correct; the rigor gap is in the plan, not the execution.

Two fixes for a v2:

1. **Smarter planner** that emits fan-out plans for ranking questions ("which X has the highest Y" pattern).
2. **A new MCP tool** like `rank_by_metric(metric, group_by_dimension)` that pushes the fan-out to the data layer where it belongs.

The eval is intentionally shallow (surface properties, refusal coverage, lever distribution). A v2 would add LLM-as-judge scoring on insight quality and a golden-set regression on numeric claims.

## Observability

Every request produces an OTEL span tree visible in Arize Phoenix at http://localhost:6006.

![Phoenix landing](docs/phoenix_landing.png)

*Phoenix Projects view showing the shelfpulse project with traced requests. Total Traces and P50 Latency are visible at a glance.*

![Phoenix trace](docs/phoenix_trace.png)

*A single /ask request expanded into nested spans. Each agent node (router, planner, tool_executor, validator, insight_builder, action_planner, finalizer) gets its own span, and the MCP tool calls (compare_periods, query_sales) appear as child spans under tool_executor. Total cost and latency surfaced for the whole trace.*

![Phoenix span detail](docs/phoenix_span.png)

*Phoenix's LLM Span Replay view. Any LLM call can be replayed with its original system prompt, input, and observed output. Sufficient to debug a misbehaving node without printf-style logging, and useful for iterating on prompts directly against captured traces.*

## Tech stack

**Backend**
- Python 3.12 with `uv` for package management
- FastAPI for the HTTP layer
- LangGraph for the 7-node agent (router, planner, tool executor, validator, insight builder, action planner, finalizer)
- Anthropic Claude Sonnet 4.5 via `langchain-anthropic`, with `with_structured_output` at every node
- FastMCP server exposing 7 tools over HTTP
- DuckDB for the synthetic warehouse (~50k rows)
- SQLite for run history and replay
- Pydantic v2 for structured outputs and request/response schemas
- Arize Phoenix plus OpenInference for OTEL tracing
- `httpx` for the eval harness

**Frontend**
- Next.js 14 App Router with TypeScript
- Tailwind CSS for styling
- Plain `fetch` against the FastAPI endpoint
- No state management library, no component library

## Repository layout

```
shelfpulse/
├── data/                  # schema.sql, seed.py
├── warehouse/             # shelfpulse.duckdb, runs.sqlite (gitignored)
├── mcp_server/            # FastMCP entry point + 7 tools + Pydantic models
├── agent/
│   ├── graph.py           # build_graph() wires every node
│   ├── state.py           # AgentState TypedDict
│   ├── llm.py             # shared ChatAnthropic factory
│   ├── guardrails.py      # input checks (PII, harmful, oversized)
│   ├── observability.py   # Phoenix bootstrap
│   ├── tool_client.py     # MCP client wrapper plus unwrap_result helper
│   ├── nodes/             # one file per node
│   └── prompts/           # system prompts for router, planner, insight, action
├── api/
│   ├── main.py            # FastAPI app with /ask, /insights, /actions, /healthz
│   ├── schemas.py         # request/response Pydantic models
│   └── storage.py         # SQLite run persistence
├── eval/
│   ├── questions.jsonl    # 10 canned questions with expected facts
│   └── run_eval.py        # grader and table printer
├── frontend/              # Next.js 14 chat UI
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
└── docs/                  # Phoenix and frontend screenshots
```

## Design choices worth calling out

**The validator is the differentiator.** Most LLM agents catch hallucination after the fact. ShelfPulse makes it structurally impossible: every aggregate number cited in an insight must come from a typed `Evidence` row produced by a real tool call. The validator builds that evidence list before the insight LLM runs. The same guarantee holds in the empty-data case — when the warehouse has no rows for a period, the tool returns zero-valued aggregates and the insight reflects the zero. The system cannot invent numbers.

**Tools are MCP, not inline.** The FastMCP server is a separate process. The same server could host a Claude desktop user, a teammate's agent, or a CLI client. The agent is one consumer, not the only consumer.

**Conservative guardrails at the boundary.** PII and prompt-injection are caught by regex before any LLM call. The router catches off-scope semantics with a single cheap LLM call. Both stages refuse with the same structured `RefusalResponse`, distinguishable by reason code.

**The action planner has Pydantic-enforced shape.** Ranks must be sequential from 1, impact ranges must satisfy `high >= low`, evidence references must match the `ev-N` pattern. The LLM cannot produce a malformed action plan even if it tries.

**Lever taxonomy matches CPG category-management standards.** The six action levers (`promo`, `assortment`, `price`, `distribution`, `planogram`, `supply`) are the classical decisions a category manager makes. They extend the 4 P's of marketing for retail: place splits into distribution and planogram, product splits into assortment and supply. A category manager reading a ShelfPulse action plan should see vocabulary they already use.

**LLM-produced fields have defaults.** Three production failures during the eval run were the same shape: a Pydantic field marked required with no default, the LLM occasionally omitted it, the request 500'd. Fields the LLM produces (confidence, generated_at) now have sensible defaults; fields the validator owns (evidence content, trace_id) stay strict.

## What's not built

- **Retry loop on the validator.** The scaffolding is there (`retry_count` in state, planner accepts feedback) but the conditional edge from validator back to planner isn't wired. A v2 would add cross-validation via redundant `compute_kpi` calls and retry on mismatch.
- **Fan-out planning.** Ranking questions ("which X has the highest Y") need the planner to emit one tool call per option. q5 in the eval suite documents this limit. A v2 adds either smarter planning or a `rank_by_metric` MCP tool.
- **Streaming response.** `/ask` is synchronous. `/ask/stream` via SSE is plumbed in the schemas but not implemented.
- **Follow-up questions.** Each /ask is stateless. A v2 would add LangGraph's `SqliteSaver` checkpointer keyed by thread_id so subsequent questions could reference the prior turn's evidence.
- **Soft enforcement of router hints.** `RouterDecision.required_tools` is produced by the router but never injected into the planner's system prompt. It exists as diagnostic data, not as a binding constraint. The planner makes its own tool choices from the question text alone. v2 would either bind the hint or remove the field.
- **Calibrated confidence.** Insight and Action `confidence` fields are self-reported by the LLM on a 0-to-1 scale. Useful for sorting within a single response, not calibrated across runs. A production v2 would either calibrate against held-out evals or replace with a derived signal like evidence-row count.
- **Authentication.** Single-tenant local demo. Production would add API key auth and row-level security at the warehouse, not in the agent.

## License and authorship

Built by Joseph Aguilar Feener.
