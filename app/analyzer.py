from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from app.config import (
    ALLOWED_CATEGORY_CODES,
    ALLOWED_PRODUCT_TAG_CODES,
    ALLOWED_SERVICE_TAG_CODES,
    CATEGORY_FALLBACK,
    CATEGORY_SYNONYMS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_SYSTEM_PROMPT,
    OPENAI_TIMEOUT_SECONDS,
    OPENAI_USER_PROMPT_TEMPLATE,
    PRODUCT_TAG_FALLBACK,
    PRODUCT_TAG_SYNONYMS,
    SERVICE_TAG_FALLBACK,
    SERVICE_TAG_SYNONYMS,
)
from app.synonyms import load_synonym_bundle

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MAX_INPUT_CHARS = 12000


def _norm_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def _normalize_from_taxonomy(
    value: Any,
    allowed_codes: list[str],
    synonyms: dict[str, str],
    fallback: str,
) -> str:
    key = _norm_key(value)
    if not key:
        return fallback

    if key in allowed_codes:
        return key

    synonym_target = synonyms.get(key)
    if synonym_target:
        return synonym_target if synonym_target in allowed_codes else fallback

    for canonical in allowed_codes:
        if key.startswith(canonical) or canonical.startswith(key):
            return canonical

    key_tokens = set(key.split("_"))
    for canonical in allowed_codes:
        canonical_tokens = set(canonical.split("_"))
        if len(key_tokens & canonical_tokens) >= 2:
            return canonical

    return fallback


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


def _raw_category_value(value: Any) -> str | None:
    raw = str(value or "").strip()
    return raw[:256] if raw else None


def _raw_tags(value: Any, *, max_items: int = 10) -> list[str]:
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
        normalized_key = _norm_key(item)
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        cleaned.append(item[:128])
        if len(cleaned) >= max_items:
            break
    return cleaned


def _normalize_tags(
    value: Any,
    *,
    allowed_codes: list[str],
    synonyms: dict[str, str],
    fallback: str,
    max_items: int = 10,
) -> list[str]:
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
        normalized = _normalize_from_taxonomy(item, allowed_codes, synonyms, fallback)
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= max_items:
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

    runtime = load_synonym_bundle()
    category_synonyms = {**CATEGORY_SYNONYMS, **runtime.category_synonyms}
    product_synonyms = {**PRODUCT_TAG_SYNONYMS, **runtime.product_synonyms}
    service_synonyms = {**SERVICE_TAG_SYNONYMS, **runtime.service_synonyms}

    allowed_category_codes = list(dict.fromkeys([*ALLOWED_CATEGORY_CODES, *sorted(runtime.category_canonicals)]))
    allowed_product_codes = list(dict.fromkeys([*ALLOWED_PRODUCT_TAG_CODES, *sorted(runtime.product_canonicals)]))
    allowed_service_codes = list(dict.fromkeys([*ALLOWED_SERVICE_TAG_CODES, *sorted(runtime.service_canonicals)]))

    normalized: list[dict] = []
    for item in flags:
        if not isinstance(item, dict):
            continue

        raw_category = _raw_category_value(item.get("category"))
        category = _normalize_from_taxonomy(
            raw_category,
            allowed_category_codes,
            category_synonyms,
            CATEGORY_FALLBACK,
        )
        raw_product_tags = _raw_tags(item.get("product_tags"))
        raw_service_tags = _raw_tags(item.get("service_tags"))
        description = str(item.get("text", "")).strip()
        if not description:
            continue

        normalized.append(
            {
                "category": category[:128],
                "raw_category": raw_category,
                "severity": _normalize_severity(item.get("severity")),
                "text": description[:4000],
                "confidence_score": _normalize_confidence(item.get("confidence_score")),
                "product_tags": _normalize_tags(
                    raw_product_tags,
                    allowed_codes=allowed_product_codes,
                    synonyms=product_synonyms,
                    fallback=PRODUCT_TAG_FALLBACK,
                ),
                "service_tags": _normalize_tags(
                    raw_service_tags,
                    allowed_codes=allowed_service_codes,
                    synonyms=service_synonyms,
                    fallback=SERVICE_TAG_FALLBACK,
                ),
                "raw_product_tags": raw_product_tags,
                "raw_service_tags": raw_service_tags,
            }
        )

    return normalized
