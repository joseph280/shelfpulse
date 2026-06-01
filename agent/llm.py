"""agent/llm.py - Shared LLM factory (provider-swappable).

All nodes call get_llm() and then .with_structured_output(...). The provider is
selected with SHELFPULSE_PROVIDER so the same code runs on a paid Anthropic key
locally and a free tier (Groq / Gemini) when deployed publicly.

  SHELFPULSE_PROVIDER=anthropic  -> reads ANTHROPIC_API_KEY  (default)
  SHELFPULSE_PROVIDER=groq       -> reads GROQ_API_KEY       (free tier)
  SHELFPULSE_PROVIDER=google     -> reads GOOGLE_API_KEY      (free tier)

Override the model name for any provider with SHELFPULSE_MODEL.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


PROVIDER = os.getenv("SHELFPULSE_PROVIDER", "anthropic").lower()

# Per-provider defaults; each is a tool-calling model that supports
# .with_structured_output(...), which every node depends on.
_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-2.0-flash",
}

MODEL = os.getenv("SHELFPULSE_MODEL") or _DEFAULT_MODELS.get(PROVIDER, "claude-sonnet-4-5")


@lru_cache(maxsize=8)
def get_llm(temperature: float = 0.2, max_tokens: int = 2048):
    """Return a cached chat model for the configured provider, keyed by
    (temperature, max_tokens). Every provider here exposes
    .with_structured_output(...)."""
    if PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model_name=MODEL,
            temperature=temperature,
            max_tokens_to_sample=max_tokens,
            timeout=None,
            stop=None,
        )

    if PROVIDER == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=MODEL,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    raise ValueError(
        f"Unknown SHELFPULSE_PROVIDER={PROVIDER!r}; expected 'anthropic', 'groq', or 'google'."
    )
