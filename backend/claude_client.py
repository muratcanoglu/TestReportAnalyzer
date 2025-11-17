# -*- coding: utf-8 -*-
"""Thin wrapper around the Anthropic Messages API."""
from __future__ import annotations

from typing import Any, Dict

from anthropic import Anthropic

try:  # pragma: no cover - prefer absolute imports in package context
    from backend.config import (
        AI_ANTHROPIC_MODEL,
        AI_MAX_TOKENS,
        AI_TIMEOUT_S,
        ANTHROPIC_API_KEY,
    )
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .config import (  # type: ignore
            AI_ANTHROPIC_MODEL,
            AI_MAX_TOKENS,
            AI_TIMEOUT_S,
            ANTHROPIC_API_KEY,
        )
    except ImportError:  # pragma: no cover - running from repository root
        from config import (  # type: ignore
            AI_ANTHROPIC_MODEL,
            AI_MAX_TOKENS,
            AI_TIMEOUT_S,
            ANTHROPIC_API_KEY,
        )

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        _client = Anthropic(api_key=ANTHROPIC_API_KEY, default_timeout=AI_TIMEOUT_S)
    return _client


def analyze_with_claude(text: str) -> Dict[str, Any]:
    """Generate a concise analysis for the provided text via Claude."""
    client = _get_client()
    message = client.messages.create(
        model=AI_ANTHROPIC_MODEL,
        max_tokens=AI_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": (
                    "Aşağıdaki test raporunu/hatayı özetle. "
                    "Kök neden analizi ve uygulanabilir çözüm önerileri ver. "
                    "Çıkışı kısa ve maddeli yaz:\n\n"
                    f"{text}"
                ),
            }
        ],
    )

    text_out = ""
    try:
        if message.content:
            block = message.content[0]
            text_out = getattr(block, "text", "") or str(block)
    except Exception:  # pragma: no cover - fallback best effort
        text_out = str(message)

    return {
        "provider": "claude",
        "model": AI_ANTHROPIC_MODEL,
        "text": (text_out or "").strip(),
    }
