# Deploying ShelfPulse

A public demo: backend in one container on **Render** (free tier), frontend on
**Vercel** (free tier), using **Anthropic** (Claude Haiku) for the LLM. The
service is protected by a password gate, so a public URL won't let strangers
spend your API budget.

Cost: hosting is free; only the Claude API calls cost money (Haiku is cheap —
fractions of a cent per query).

Trade-off you've accepted: the free backend **sleeps after ~15 min idle** and
cold-starts in ~30–60s. Once warm it's responsive.

---

## 0. One-time: get an Anthropic API key

Create a key at <https://console.anthropic.com> → **API Keys** (starts with
`sk-ant-...`). Also decide a gate password (default in examples: `shelfpulse`).

---

## 1. Backend → Render (Docker)

The repo already has a `Dockerfile`, `start.sh`, and `render.yaml`. The image
runs the MCP server (internal `127.0.0.1:8001`) and the FastAPI app together,
and bakes the synthetic DuckDB warehouse at build time.

1. Push this repo to GitHub (see "Commit & push" below).
2. In Render: **New → Blueprint**, pick this repo. Render reads `render.yaml`.
3. Before the first deploy, set the secret env vars (marked `sync: false`):
   - `ANTHROPIC_API_KEY` = your `sk-ant-...` key
   - `APP_PASSWORD` = the gate password (e.g. `shelfpulse`)
   - `ALLOWED_ORIGINS` = your Vercel URL (set after step 2; start with `*` if unsure)
4. Deploy. When it's live you get a URL like `https://shelfpulse-api.onrender.com`.
5. Sanity check: open `https://<your-render-url>/healthz` — you want
   `"status":"ok"`, `"llm_provider":"anthropic"`, `"llm_key":"ANTHROPIC_API_KEY present"`,
   and a non-zero `warehouse_rows`. (`/healthz` is public; `/ask` requires the password.)

The env vars baked in by `render.yaml`:

| Var | Value | Why |
|---|---|---|
| `SHELFPULSE_PROVIDER` | `anthropic` | LLM backend |
| `SHELFPULSE_MODEL` | `claude-haiku-4-5` | Cheapest model with reliable structured output |
| `PHOENIX_COLLECTOR_ENDPOINT` | `https://app.phoenix.arize.com` | Stream traces to Phoenix Cloud |
| `PHOENIX_API_KEY` | *(secret)* | Phoenix Cloud key (see step 1a) |
| `ANTHROPIC_API_KEY` | *(secret)* | Your key |
| `APP_PASSWORD` | *(secret)* | Password required to use `/ask` |
| `ALLOWED_ORIGINS` | *(your Vercel URL)* | CORS allowlist for the frontend |

### 1a. Observability → Phoenix Cloud (optional but recommended)

Traces stream to a hosted Phoenix so you can inspect every request online.

1. Sign up at <https://app.phoenix.arize.com> → **Settings → API Keys** → create a key.
2. Set `PHOENIX_API_KEY` in Render (above). `PHOENIX_COLLECTOR_ENDPOINT` is already
   set by `render.yaml`.
3. Copy your Phoenix **project URL** (open the `shelfpulse` project; the URL looks
   like `https://app.phoenix.arize.com/projects/<id>`) — you'll give this to Vercel
   in step 2 as `NEXT_PUBLIC_PHOENIX_URL` so the "view in Phoenix" links work.

> Skip this and tracing is simply off in prod (the app still works; the in-app
> "view in Phoenix" links just won't render).

> Not using the Blueprint? Create a **Web Service → Docker**, same env vars,
> health check path `/healthz`.

> **Hugging Face Spaces** works too: create a **Docker** Space, push this repo,
> add the same vars as Space secrets. HF Spaces stay warm longer than Render free.

---

## 2. Frontend → Vercel (free)

The frontend already reads `NEXT_PUBLIC_API_BASE` (falls back to localhost), so
no code change — just point it at the Render URL.

1. In Vercel: **Add New → Project**, import this repo.
2. **Root Directory → `frontend`** (important — the Next.js app lives there).
3. Add environment variables:
   - `NEXT_PUBLIC_API_BASE` = `https://<your-render-url>` (no trailing slash)
   - `NEXT_PUBLIC_PHOENIX_URL` = your Phoenix project URL from step 1a (optional;
     enables the "view in Phoenix" links). Omit it and those links are hidden.
4. Deploy. You get a URL like `https://shelfpulse.vercel.app`.
5. Go back to Render and set `ALLOWED_ORIGINS` to that exact Vercel URL, then
   redeploy the backend (or trigger a manual deploy). Now the browser is allowed
   to call the API.

---

## 3. Try it

Open the Vercel URL and ask a question. First request after idle will be slow
(backend cold start); after that it's fast.

---

## Local development is unchanged

Locally you still run on Anthropic — nothing about your dev flow changed:

```bash
# Terminal 1
uv run python -m mcp_server.server
# Terminal 2
uv run uvicorn api.main:app --port 8000
# Terminal 3
cd frontend && npm run dev
```

To test the Gemini path locally, prefix with the env vars:

```bash
SHELFPULSE_PROVIDER=google GOOGLE_API_KEY=AIza... SHELFPULSE_MODEL=gemini-2.0-flash \
  uv run uvicorn api.main:app --port 8000
```

> Note: your local `.env` sets `SHELFPULSE_MODEL=claude-sonnet-4-5`. That value
> wins over the provider default, so when running on Gemini either unset it or
> override it with a Gemini model name (as shown above). The Render deploy already
> sets the correct Gemini model.

---

## Switching providers later

`agent/llm.py` supports three providers via `SHELFPULSE_PROVIDER`:

| Provider | Env var for key | Default model | Extra dep |
|---|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5` | (installed) |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | (installed) |
| `google` | `GOOGLE_API_KEY` | `gemini-2.0-flash` | (installed) |
