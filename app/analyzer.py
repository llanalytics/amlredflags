from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from app.config import (
    ALLOWED_CATEGORY_CODES,
    CATEGORY_FALLBACK,
    CATEGORY_SYNONYMS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_SYSTEM_PROMPT,
    OPENAI_TIMEOUT_SECONDS,
    OPENAI_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MAX_INPUT_CHARS = 12000


def _category_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def _normalize_category(value: Any) -> str:
    key = _category_key(value)
    if not key:
        return CATEGORY_FALLBACK

    if key in ALLOWED_CATEGORY_CODES:
        return key

    synonym_target = CATEGORY_SYNONYMS.get(key)
    if synonym_target:
        return synonym_target if synonym_target in ALLOWED_CATEGORY_CODES else CATEGORY_FALLBACK

    # Lightweight fuzzy fallback: "startswith"/token containment on canonical keys.
    for canonical in ALLOWED_CATEGORY_CODES:
        if key.startswith(canonical) or canonical.startswith(key):
            return canonical

    key_tokens = set(key.split("_"))
    for canonical in ALLOWED_CATEGORY_CODES:
        canonical_tokens = set(canonical.split("_"))
        overlap = len(key_tokens & canonical_tokens)
        if overlap >= 2:
            return canonical

    return CATEGORY_FALLBACK


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


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []

    raw_items: list[str]
    if isinstance(value, list):
        raw_items = [str(v).strip() for v in value]
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    else:
        raw_items = [str(value).strip()]

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        normalized = item[:64]
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
        if len(cleaned) >= 10:
            break
    return cleaned


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

        category = _normalize_category(item.get("category"))
        description = str(item.get("text", "")).strip()
        if not description:
            continue

        normalized.append(
            {
                "category": category[:128],
                "severity": _normalize_severity(item.get("severity")),
                "text": description[:4000],
                "confidence_score": _normalize_confidence(item.get("confidence_score")),
                "product_tags": _normalize_tags(item.get("product_tags")),
                "service_tags": _normalize_tags(item.get("service_tags")),
            }
        )

    return normalized
