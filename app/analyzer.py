from __future__ import annotations

import json
import logging
from typing import Any

import requests

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_SYSTEM_PROMPT,
    OPENAI_TIMEOUT_SECONDS,
    OPENAI_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MAX_INPUT_CHARS = 12000


def _normalize_severity(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"high", "medium", "low"}:
        return raw
    return "medium"


def _normalize_confidence(value: Any) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, n))


def _build_prompt(text: str) -> list[dict[str, str]]:
    truncated_text = text[:MAX_INPUT_CHARS]
    user_prompt = OPENAI_USER_PROMPT_TEMPLATE
    if "{document_text}" in user_prompt:
        user_prompt = user_prompt.replace("{document_text}", truncated_text)
    else:
        user_prompt = f"{user_prompt}\n\n{truncated_text}"

    return [
        {
            "role": "system",
            "content": OPENAI_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _call_openai(messages: list[dict[str, str]]) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    response = requests.post(
        OPENAI_API_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": messages,
        },
        timeout=OPENAI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def extract_red_flags(text: str) -> list[dict]:
    """
    Extract AML red flags via OpenAI and normalize output for persistence.
    """
    payload = _call_openai(_build_prompt(text))
    flags = payload.get("flags", [])
    if not isinstance(flags, list):
        raise RuntimeError("OpenAI response missing valid 'flags' array")

    normalized: list[dict] = []
    for item in flags:
        if not isinstance(item, dict):
            continue

        category = str(item.get("category", "")).strip()
        description = str(item.get("text", "")).strip()
        if not category or not description:
            continue

        normalized.append(
            {
                "category": category[:128],
                "severity": _normalize_severity(item.get("severity")),
                "text": description[:4000],
                "confidence_score": _normalize_confidence(item.get("confidence_score")),
            }
        )

    return normalized
