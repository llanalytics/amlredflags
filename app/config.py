import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional local dependency
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "amlredflags_v2.db"
if load_dotenv:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)


def get_database_url() -> str:
    raw = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw.startswith("sqlite:///"):
        sqlite_path = raw.replace("sqlite:///", "", 1)
        if sqlite_path != ":memory:" and not sqlite_path.startswith("/"):
            return f"sqlite:///{(PROJECT_ROOT / sqlite_path).resolve()}"
    return raw


def _csv_list_env(name: str, default_values: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default_values
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        value = part.strip().lower().replace(" ", "_")
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out or default_values


def _json_dict_env(name: str, default_value: dict[str, str]) -> dict[str, str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default_value
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default_value
    if not isinstance(parsed, dict):
        return default_value

    normalized: dict[str, str] = {}
    for k, v in parsed.items():
        key = str(k).strip().lower().replace(" ", "_")
        value = str(v).strip().lower().replace(" ", "_")
        if key and value:
            normalized[key] = value
    return normalized or default_value


DATABASE_URL = get_database_url()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DB_SCHEMA = None if DATABASE_URL.startswith("sqlite") else os.getenv("DB_SCHEMA", "amlredflags_v2")
MAX_PAGES_PER_SOURCE = int(os.getenv("MAX_PAGES_PER_SOURCE", "3"))
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "30"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))

DEFAULT_CATEGORY_CODES = [
    "structuring",
    "trade_based_money_laundering",
    "shell_company_misuse",
    "beneficial_ownership_obfuscation",
    "high_risk_jurisdiction_exposure",
    "sanctions_evasion_indicators",
    "funnel_account_activity",
    "cash_intensive_anomaly",
    "third_party_payment_misuse",
    "transaction_velocity_spike",
    "document_forgery_or_false_records",
    "insider_collusion_or_employee_misconduct",
    "correspondent_banking_risk",
    "crypto_asset_laundering_pattern",
    "other_suspicious_activity",
]

DEFAULT_CATEGORY_SYNONYMS = {
    "smurfing": "structuring",
    "structuring_transactions": "structuring",
    "tbml": "trade_based_money_laundering",
    "trade_based_ml": "trade_based_money_laundering",
    "shell_company": "shell_company_misuse",
    "ubo_obfuscation": "beneficial_ownership_obfuscation",
    "beneficial_ownership_hiding": "beneficial_ownership_obfuscation",
    "high_risk_jurisdiction": "high_risk_jurisdiction_exposure",
    "sanctions_circumvention": "sanctions_evasion_indicators",
    "layering": "other_suspicious_activity",
    "placement": "other_suspicious_activity",
    "integration": "other_suspicious_activity",
}

ALLOWED_CATEGORY_CODES = _csv_list_env("ALLOWED_CATEGORY_CODES", DEFAULT_CATEGORY_CODES)
CATEGORY_SYNONYMS = _json_dict_env("CATEGORY_SYNONYMS_JSON", DEFAULT_CATEGORY_SYNONYMS)
CATEGORY_FALLBACK = os.getenv("CATEGORY_FALLBACK", "other_suspicious_activity").strip().lower().replace(" ", "_")
if CATEGORY_FALLBACK not in ALLOWED_CATEGORY_CODES:
    ALLOWED_CATEGORY_CODES = [*ALLOWED_CATEGORY_CODES, CATEGORY_FALLBACK]

OPENAI_SYSTEM_PROMPT = os.getenv(
    "OPENAI_SYSTEM_PROMPT",
    (
        "You are an AML analyst. Identify only explicit or clearly implied "
        "money-laundering risks and descriptions of how a financial crime occurred. "
        "The document must describe specific products or services or assets types used in a financial crime, or specific techniques used to launder money, or specific behaviors of customers or employees that were part of a financial crime. "
        "Use one of these canonical category codes when assigning category: "
        + ", ".join(ALLOWED_CATEGORY_CODES)
        + ". "
        "Return strict JSON with this shape: "
        '{"flags":[{"category":"string","severity":"high|medium|low","text":"string","confidence_score":0-100,"product_tags":["string"],"service_tags":["string"]}]}. '
        'If there are no credible risks, return {"flags":[]}. '
        "Do not include markdown or any extra keys."
    ),
).replace("\\n", "\n")
OPENAI_USER_PROMPT_TEMPLATE = os.getenv(
    "OPENAI_USER_PROMPT_TEMPLATE",
    (
        "Analyze this document text for AML risks and financial-crime mechanisms.\n\n"
        "{document_text}"
    ),
).replace("\\n", "\n")
RESET_API_TOKEN = os.getenv("RESET_API_TOKEN", "")

SOURCES = [
    {"name": "FinCEN News", "url": "https://www.fincen.gov/news", "max_pages": 3, "max_articles": 30},
    {"name": "FinCEN Enforcement", "url": "https://www.fincen.gov/news/enforcement-actions", "max_pages": 3, "max_articles": 30},
    {"name": "OCC Newsroom", "url": "https://www.occ.gov/news-events/newsroom", "max_pages": 3, "max_articles": 30},
]
