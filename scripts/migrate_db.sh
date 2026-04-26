#!/bin/bash
# Migrate amlredflags database safely.
# Usage:
#   ./scripts/migrate_db.sh [local|remote|database-url] [auto|upgrade|stamp]
#
# Examples:
#   ./scripts/migrate_db.sh local
#   ./scripts/migrate_db.sh remote
#   ./scripts/migrate_db.sh remote upgrade
#   ./scripts/migrate_db.sh sqlite:////tmp/aml.db stamp

set -euo pipefail

TARGET="${1:-local}"
ACTION="${2:-auto}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
PATH="$PROJECT_ROOT/.venv/bin:$PATH"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if ! command -v alembic >/dev/null 2>&1; then
  echo -e "${RED}Error: alembic is required in PATH.${NC}"
  exit 1
fi

# Load only required keys from .env without shell-sourcing.
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue
        ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    case "$key" in
      DATABASE_URL)
        if [ -z "${DATABASE_URL:-}" ]; then DATABASE_URL="$value"; fi
        ;;
      LOCAL_DATABASE_URL)
        if [ -z "${LOCAL_DATABASE_URL:-}" ]; then LOCAL_DATABASE_URL="$value"; fi
        ;;
      DB_SCHEMA)
        if [ -z "${DB_SCHEMA:-}" ]; then DB_SCHEMA="$value"; fi
        ;;
    esac
  done < "$ENV_FILE"
fi

resolve_db_url() {
  case "$TARGET" in
    local)
      if [ -n "${LOCAL_DATABASE_URL:-}" ]; then
        printf '%s\n' "$LOCAL_DATABASE_URL"
      elif [ -n "${DATABASE_URL:-}" ] && [[ "${DATABASE_URL:-}" == sqlite* ]]; then
        printf '%s\n' "$DATABASE_URL"
      else
        printf 'sqlite:///%s/amlredflags_v2.db\n' "$PROJECT_ROOT"
      fi
      ;;
    remote)
      if [ -z "${DATABASE_URL:-}" ]; then
        return 1
      fi
      printf '%s\n' "$DATABASE_URL"
      ;;
    *)
      if [[ "$TARGET" == *"://"* ]]; then
        printf '%s\n' "$TARGET"
      else
        return 1
      fi
      ;;
  esac
}

if ! DB_URL="$(resolve_db_url)"; then
  echo -e "${RED}Error: could not resolve DATABASE_URL for target '$TARGET'.${NC}"
  echo "Set DATABASE_URL/LOCAL_DATABASE_URL in .env, or pass a full database URL."
  exit 1
fi

export DATABASE_URL="$DB_URL"

if [ "$TARGET" = "local" ] && [ -n "${LOCAL_DATABASE_URL:-}" ]; then
  export DATABASE_URL="$LOCAL_DATABASE_URL"
fi

DECIDE_ACTION_PY='
import os
from sqlalchemy import create_engine, inspect

url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

schema = os.environ.get("DB_SCHEMA", "").strip() or None
engine = create_engine(url)
insp = inspect(engine)

version_table = "alembic_version_amlredflags_v2"
core_tables = ("batch_runs", "source_documents", "red_flags")

has_version = insp.has_table(version_table, schema=schema)
has_core = all(insp.has_table(t, schema=schema) for t in core_tables)

if has_version:
    print("upgrade")
elif has_core:
    print("stamp")
else:
    print("upgrade")
'

if [ "$ACTION" = "auto" ]; then
  if ACTION_RESOLVED="$(python -c "$DECIDE_ACTION_PY" 2>/dev/null)"; then
    ACTION="$ACTION_RESOLVED"
  else
    ACTION="upgrade"
  fi
fi

if [ "$ACTION" != "upgrade" ] && [ "$ACTION" != "stamp" ]; then
  echo -e "${RED}Error: action must be one of auto|upgrade|stamp.${NC}"
  exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AML Red Flags v2 - DB Migration${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Target: $TARGET"
echo "DATABASE_URL: $DATABASE_URL"
echo "DB_SCHEMA: ${DB_SCHEMA:-"(default)"}"
echo "Action: $ACTION"
echo ""

cd "$PROJECT_ROOT"
if [ "$ACTION" = "stamp" ]; then
  echo -e "${YELLOW}Stamping current schema as head...${NC}"
  alembic stamp head
else
  echo -e "${GREEN}Applying migrations...${NC}"
  alembic upgrade head
fi

echo ""
echo -e "${GREEN}Done.${NC}"
