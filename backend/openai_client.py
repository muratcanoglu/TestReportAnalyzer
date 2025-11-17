# -*- coding: utf-8 -*-
"""Thin wrapper around the OpenAI Responses API."""
from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

try:  # pragma: no cover - prefer absolute imports under package execution
    from backend.config import AI_MAX_TOKENS, AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .config import (  # type: ignore
            AI_MAX_TOKENS,
            AI_OPENAI_MODEL,
            AI_TIMEOUT_S,
            OPENAI_API_KEY,
        )
    except ImportError:  # pragma: no cover - running from repository root
        from config import (  # type: ignore
            AI_MAX_TOKENS,
            AI_OPENAI_MODEL,
            AI_TIMEOUT_S,
            OPENAI_API_KEY,
        )

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing")
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=AI_TIMEOUT_S)
    return _client


def analyze_with_openai(text: str) -> Dict[str, Any]:
    """Generate a concise analysis for the provided text via OpenAI."""
    client = _get_client()
    response = client.responses.create(
        model=AI_OPENAI_MODEL,
        max_output_tokens=AI_MAX_TOKENS,
        input=(
            "Aşağıdaki test raporunu/hatayı özetle. "
            "Kök neden analizi ve uygulanabilir çözüm önerileri ver. "
            "Çıkışı kısa ve maddeli yaz:\n\n"
            f"{text}"
        ),
    )

    output_text = getattr(response, "output_text", None)
    if output_text is None:
        try:
            parts = []
            for item in getattr(response, "output", []) or []:
                content = getattr(item, "content", None)
                if content is None:
                    parts.append(str(item))
                    continue
                if isinstance(content, (list, tuple)):
                    for block in content:
                        block_text = getattr(block, "text", None)
                        if block_text:
                            parts.append(str(block_text))
                else:
                    parts.append(str(content))
            output_text = "\n".join(parts)
        except Exception:  # pragma: no cover - fallback best effort
            output_text = str(response)

    return {
        "provider": "chatgpt",
        "model": AI_OPENAI_MODEL,
        "text": (output_text or "").strip(),
    }
