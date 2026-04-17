from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.config import DB_SCHEMA
from app.database import SessionLocal, engine
from app.models import RedFlagSynonym

logger = logging.getLogger(__name__)


@dataclass
class SynonymBundle:
    category_synonyms: dict[str, str] = field(default_factory=dict)
    product_synonyms: dict[str, str] = field(default_factory=dict)
    service_synonyms: dict[str, str] = field(default_factory=dict)
    category_canonicals: set[str] = field(default_factory=set)
    product_canonicals: set[str] = field(default_factory=set)
    service_canonicals: set[str] = field(default_factory=set)


_CACHE_TTL_SECONDS = max(5, int(os.getenv("SYNONYM_CACHE_TTL_SECONDS", "60")))
_cache_expires_at = 0.0
_cached_bundle = SynonymBundle()
_table_exists: bool | None = None


def _norm_key(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def _check_table_exists() -> bool:
    global _table_exists
    if _table_exists is not None:
        return _table_exists
    try:
        insp = inspect(engine)
        schema = DB_SCHEMA if engine.dialect.name != "sqlite" else None
        _table_exists = bool(insp.has_table("red_flag_synonyms", schema=schema))
    except Exception:
        _table_exists = False
    return _table_exists


def load_synonym_bundle() -> SynonymBundle:
    global _cache_expires_at, _cached_bundle

    now = time.monotonic()
    if now < _cache_expires_at:
        return _cached_bundle

    if not _check_table_exists():
        _cached_bundle = SynonymBundle()
        _cache_expires_at = now + _CACHE_TTL_SECONDS
        return _cached_bundle

    db = SessionLocal()
    try:
        rows = (
            db.query(RedFlagSynonym)
            .filter(RedFlagSynonym.is_active == True)  # noqa: E712
            .all()
        )

        bundle = SynonymBundle()
        for row in rows:
            scope = _norm_key(row.scope)
            raw_key = _norm_key(row.raw_value_key or row.raw_value)
            canonical = _norm_key(row.canonical_value)
            if not scope or not raw_key or not canonical:
                continue

            if scope == "category":
                bundle.category_synonyms[raw_key] = canonical
                bundle.category_canonicals.add(canonical)
            elif scope == "product":
                bundle.product_synonyms[raw_key] = canonical
                bundle.product_canonicals.add(canonical)
            elif scope == "service":
                bundle.service_synonyms[raw_key] = canonical
                bundle.service_canonicals.add(canonical)

        _cached_bundle = bundle
        _cache_expires_at = now + _CACHE_TTL_SECONDS
        return _cached_bundle
    except SQLAlchemyError as exc:
        logger.warning("Failed to load red flag synonyms from DB: %s", exc)
        _cached_bundle = SynonymBundle()
        _cache_expires_at = now + _CACHE_TTL_SECONDS
        return _cached_bundle
    finally:
        db.close()
