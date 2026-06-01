# Deploying ShelfPulse for free

A fully public, **$0** demo: backend in one container on **Render** (free tier),
frontend on **Vercel** (free tier), and a **free Gemini** key for the LLM so no
request ever costs money.

Trade-off you've accepted: the free backend **sleeps after ~15 min idle** and
cold-starts in ~30–60s. Once warm it's responsive.

---

## 0. One-time: get a Gemini API key

> A "Gemini Pro" consumer subscription is **not** an API key. You need an API
> key from Google AI Studio (its free tier is plenty for this demo).

1. Go to <https://aistudio.google.com/app/apikey> and sign in.
2. **Create API key**. Copy it (starts with `AIza...`).

That's the only credential you need.

---

## 1. Backend → Render (Docker, free)

The repo already has a `Dockerfile`, `start.sh`, and `render.yaml`. The image
runs the MCP server (internal `127.0.0.1:8001`) and the FastAPI app together,
and bakes the synthetic DuckDB warehouse at build time.

1. Push this repo to GitHub (see "Commit & push" below).
2. In Render: **New → Blueprint**, pick this repo. Render reads `render.yaml`.
3. Before the first deploy, set the two secret env vars (marked `sync: false`):
   - `GOOGLE_API_KEY` = your `AIza...` key
   - `ALLOWED_ORIGINS` = your Vercel URL (set after step 2; start with `*` if unsure)
4. Deploy. When it's live you get a URL like `https://shelfpulse-api.onrender.com`.
5. Sanity check: open `https://<your-render-url>/healthz` — you want
   `"status":"ok"`, `"llm_provider":"google"`, `"llm_key":"GOOGLE_API_KEY present"`,
   and a non-zero `warehouse_rows`.

The env vars baked in by `render.yaml`:

| Var | Value | Why |
|---|---|---|
| `SHELFPULSE_PROVIDER` | `google` | Use the free Gemini tier instead of Anthropic |
| `SHELFPULSE_MODEL` | `gemini-2.0-flash` | Gemini tool-calling model (bump to `gemini-2.5-pro` if desired) |
| `PHOENIX_DISABLED` | `1` | Don't launch the local tracing UI in prod |
| `GOOGLE_API_KEY` | *(secret)* | Your key |
| `ALLOWED_ORIGINS` | *(your Vercel URL)* | CORS allowlist for the frontend |

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
3. Add an environment variable:
   - `NEXT_PUBLIC_API_BASE` = `https://<your-render-url>` (no trailing slash)
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
