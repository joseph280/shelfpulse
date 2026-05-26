"""agent/observability.py - Arize Phoenix tracing setup.

Phoenix runs locally as a process; we boot it programmatically at
service startup, register a tracer, and turn on LangChain
auto-instrumentation. Every LLM call and tool invocation downstream
of this point produces an OTEL span visible at http://localhost:6006.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("shelfpulse.observability")


def setup_phoenix() -> Any | None:
    """Launch Phoenix and register the OTEL tracer.

    Returns the running Phoenix session, or None if Phoenix is
    disabled via the PHOENIX_DISABLED env var. Safe to call multiple
    times; subsequent calls are no-ops.
    """
    if os.getenv("PHOENIX_DISABLED", "").lower() in ("1", "true", "yes"):
        log.info("Phoenix tracing is disabled via PHOENIX_DISABLED.")
        return None
    
    try:
        import phoenix as px
        from phoenix.otel import register
    except ImportError as exc:
        log.warning("Phoenix is not installed; tracing is disabled. Install with `pip install shelfpulse[observability]`.")
        return None
    
    port = int(os.getenv("PHOENIX_PORT", "6006"))
    os.environ["PHOENIX_PORT"] = str(port)
    session = px.launch_app()    

    url = getattr(session, "url", f"http://localhost:{port}")
    log.info("Phoenix UI: %s", url)

    register(
        project_name="shelfpulse",
        auto_instrument=True,
        batch=True
    )
    log.info("LangChain auto-instrumentation enabled.")

    return session
