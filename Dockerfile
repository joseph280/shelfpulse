# ShelfPulse backend — MCP server + FastAPI agent in one container.
# Designed for free single-instance hosts (Render, Hugging Face Spaces, Fly.io).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Phoenix tracing launches a local UI server; off by default in prod.
    PHOENIX_DISABLED=1

WORKDIR /app

# Install dependencies first (cached unless lockfile changes), prod only.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source.
COPY . .

# Finish installing the project itself now that the source is present.
RUN uv sync --frozen --no-dev

# Bake the synthetic warehouse into the image. The filesystem is ephemeral on
# free tiers, so building the DuckDB file here means it always exists at boot.
RUN uv run python data/seed.py

# Render/HF inject $PORT; default to 8000 for plain `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["./start.sh"]
