import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "amlredflags_v2.db"
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
MAX_PAGES_PER_SOURCE = int(os.getenv("MAX_PAGES_PER_SOURCE", "3"))

SOURCES = [
    {"name": "FinCEN News", "url": "https://www.fincen.gov/news", "max_pages": 3},
    {"name": "FinCEN Enforcement", "url": "https://www.fincen.gov/news/enforcement-actions", "max_pages": 3},
    {"name": "OCC Newsroom", "url": "https://www.occ.gov/news-events/newsroom", "max_pages": 3},
]
