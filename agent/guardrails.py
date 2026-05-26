"""agent/guardrails.py - Pre-graph input checks.

These guards run before the agent graph is invoked. They catch the
classes of input that the router's LLM-based scope check is not
designed for: oversized payloads, PII leakage, and obvious harmful
intent. Each guard returns either None (pass) or a RefusalResponse.

Structural guarantees inside the graph (Pydantic schemas, evidence-
constrained insights, structured outputs at every node) handle the
correctness side. These guards handle the input-hygiene side.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from api.schemas import RefusalResponse


MAX_QUESTION_LENGTH = 2000

# Patterns that strongly suggest PII in the question.
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\b\+?1?[ -]?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b")),
]

# Patterns suggesting prompt-injection or harmful intent.
_HARM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore (all |any |previous |prior )?(instructions|rules)\b", re.I),
    re.compile(r"\b(system prompt|reveal your prompt|show me your prompt)\b", re.I),
    re.compile(r"\b(make a bomb|kill|attack instructions|exploit)\b", re.I),
    re.compile(r"\b(?:jailbreak|DAN mode|developer mode)\b", re.I),
]


def _refuse(
        reason: Literal["out_of_scope", "harmful", "pii", "oversized_input"],
        message: str
) -> RefusalResponse:
    return RefusalResponse(
        trace_id=uuid.uuid4().hex[:12],
        reason=reason,
        message=message
    )


def check_input(question: str) -> RefusalResponse | None:
    """Run all pre-graph guards. Return a RefusalResponse on failure, else None."""
    if not question or len(question.strip()) < 3:
        return _refuse(
            "oversized_input",
            "Please send a question of at least a few characters.",
        )

    if len(question) > MAX_QUESTION_LENGTH:
        return _refuse(
            "oversized_input",
            f"Your question is too long ({len(question)} characters). "
            f"Please limit it to {MAX_QUESTION_LENGTH} characters or fewer."
        )
    
    for label, pattern in _PII_PATTERNS:
        if pattern.search(question):
            return _refuse(
                "pii",
                f"Your question appears to contain {label} personally identifiable information (PII). "
                "Please remove any sensitive information and try again."
            )
        
    for pattern in _HARM_PATTERNS:
        if pattern.search(question):
            return _refuse(
                "harmful",
                "Your question appears to contain harmful or malicious intent. "
                "Please rephrase your question and avoid any content that suggests violence, illegal activity, or prompt injection."
            )
        
    return None