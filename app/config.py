import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional local dependency
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "amlredflags_v2.db"
if load_dotenv:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)


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


DATABASE_URL = get_database_url()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DB_SCHEMA = None if DATABASE_URL.startswith("sqlite") else os.getenv("DB_SCHEMA", "amlredflags_v2")
MAX_PAGES_PER_SOURCE = int(os.getenv("MAX_PAGES_PER_SOURCE", "3"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
OPENAI_SYSTEM_PROMPT = os.getenv(
    "OPENAI_SYSTEM_PROMPT",
    (
        "You are an AML analyst. Identify only explicit or clearly implied "
        "money-laundering risks and descriptions of how a financial crime occurred. "
        "Return strict JSON with this shape: "
        '{"flags":[{"category":"string","severity":"high|medium|low","text":"string","confidence_score":0-100}]}. '
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
    {"name": "FinCEN News", "url": "https://www.fincen.gov/news", "max_pages": 3},
    {"name": "FinCEN Enforcement", "url": "https://www.fincen.gov/news/enforcement-actions", "max_pages": 3},
    {"name": "OCC Newsroom", "url": "https://www.occ.gov/news-events/newsroom", "max_pages": 3},
]
