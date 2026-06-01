"""agent/observability.py - Arize Phoenix tracing setup.

Two modes:

* **Local** (default for dev): boots an embedded Phoenix UI via
  ``px.launch_app()`` on ``PHOENIX_PORT`` (default 6006).
* **Remote / Phoenix Cloud** (for deployment): when
  ``PHOENIX_COLLECTOR_ENDPOINT`` is set, traces are exported to that
  collector instead of launching a local UI — so you can view them at a
  real online URL (e.g. https://app.phoenix.arize.com). Set
  ``PHOENIX_API_KEY`` for authenticated collectors like Phoenix Cloud.

Set ``PHOENIX_DISABLED=1`` to turn tracing off entirely.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("shelfpulse.observability")


def setup_phoenix() -> Any | None:
    """Launch or connect Phoenix and register the OTEL tracer.

    Returns the running Phoenix session in local mode, or None in remote /
    disabled mode. Safe to call once at startup.
    """
    if os.getenv("PHOENIX_DISABLED", "").lower() in ("1", "true", "yes"):
        log.info("Phoenix tracing is disabled via PHOENIX_DISABLED.")
        return None

    try:
        from phoenix.otel import register
    except ImportError:
        log.warning("Phoenix is not installed; tracing is disabled.")
        return None

    collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")

    if collector:
        # Remote mode: export traces to a hosted collector (e.g. Phoenix Cloud).
        # register() reads PHOENIX_COLLECTOR_ENDPOINT + PHOENIX_CLIENT_HEADERS
        # from the environment. Translate PHOENIX_API_KEY into the auth header.
        api_key = os.getenv("PHOENIX_API_KEY")
        if api_key and not os.getenv("PHOENIX_CLIENT_HEADERS"):
            os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={api_key}"
        register(project_name="shelfpulse", auto_instrument=True, batch=True)
        log.info("Phoenix tracing -> %s (project=shelfpulse)", collector)
        return None

    # Local mode: launch the embedded Phoenix UI.
    import phoenix as px

    port = int(os.getenv("PHOENIX_PORT", "6006"))
    os.environ["PHOENIX_PORT"] = str(port)
    session = px.launch_app()
    url = getattr(session, "url", f"http://localhost:{port}")
    log.info("Phoenix UI: %s", url)

    register(project_name="shelfpulse", auto_instrument=True, batch=True)
    log.info("LangChain auto-instrumentation enabled.")
    return session


def current_trace_id() -> str | None:
    """Return the active OpenTelemetry trace ID as a 32-char hex string, or
    None if there is no recording span (tracing off, or called outside a span).

    This is the ID Phoenix uses to identify a trace, so it can be used to deep
    link into the Phoenix UI.
    """
    try:
        from opentelemetry import trace as otel_trace
    except ImportError:
        return None

    span = otel_trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id:  # 0 == no/invalid trace
        return None
    return format(ctx.trace_id, "032x")
