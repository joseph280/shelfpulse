"""agent/llm.py - Shared Anthropic LLM factory.
All nodes use the same model and the same low temperature. Override
the model name with the SHELFPULSE_MODEL env var if needed.
"""

from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic



load_dotenv()


MODEL = os.getenv("SHELFPULSE_MODEL", "claude-sonnet-4-5")



@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.2, max_tokens: int = 2048) -> ChatAnthropic:
    """Return a cached ChatAnthropic instance keyed by (temperature, max_tokens)."""
    return ChatAnthropic( 
        model_name=MODEL,
        temperature=temperature,
        max_tokens_to_sample=max_tokens,
        timeout=None,
        stop=None
    )