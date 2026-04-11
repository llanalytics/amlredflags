#!/usr/bin/env bash
# Migrate amlredflags tables from one PostgreSQL schema to another.
#
# Usage:
#   ./scripts/migrate_to_schema.sh [local|remote|database-url] [source_schema] [target_schema] [--execute]
#
# Examples:
#   ./scripts/migrate_to_schema.sh remote public amlredflags
#   ./scripts/migrate_to_schema.sh remote public amlredflags --execute
#   ./scripts/migrate_to_schema.sh postgres://... public amlredflags --execute

set -euo pipefail

TARGET="${1:-remote}"
SOURCE_SCHEMA="${2:-public}"
TARGET_SCHEMA="${3:-amlredflags}"
EXECUTE_FLAG="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [ "$SOURCE_SCHEMA" = "$TARGET_SCHEMA" ]; then
  echo "Source and target schema are the same: '$SOURCE_SCHEMA'. Nothing to do."
  exit 0
fi

if [[ ! "$SOURCE_SCHEMA" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "Invalid source schema: $SOURCE_SCHEMA"
  exit 1
fi

if [[ ! "$TARGET_SCHEMA" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "Invalid target schema: $TARGET_SCHEMA"
  exit 1
fi

# Load URLs from .env if present (without sourcing shell code)
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"

    case "$key" in
      DATABASE_URL)
        [ -z "${DATABASE_URL:-}" ] && DATABASE_URL="$value"
        ;;
      LOCAL_DATABASE_URL)
        [ -z "${LOCAL_DATABASE_URL:-}" ] && LOCAL_DATABASE_URL="$value"
        ;;
    esac
  done < "$ENV_FILE"
fi

resolve_db_url() {
  case "$TARGET" in
    local)
      if [ -n "${LOCAL_DATABASE_URL:-}" ]; then
        printf '%s\n' "$LOCAL_DATABASE_URL"
      elif [ -n "${DATABASE_URL:-}" ]; then
        printf '%s\n' "$DATABASE_URL"
      else
        return 1
      fi
      ;;
    remote)
      if [ -n "${DATABASE_URL:-}" ]; then
        printf '%s\n' "$DATABASE_URL"
      else
        return 1
      fi
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
  echo "Could not resolve database URL for target '$TARGET'."
  echo "Set DATABASE_URL/LOCAL_DATABASE_URL in .env, or pass a full database URL."
  exit 1
fi

if [[ "$DB_URL" == sqlite* ]]; then
  echo "This schema migration is for PostgreSQL only; got sqlite URL."
  exit 1
fi

export DATABASE_URL="$DB_URL"
export SOURCE_SCHEMA
export TARGET_SCHEMA
export EXECUTE_MODE="false"
if [ "$EXECUTE_FLAG" = "--execute" ]; then
  export EXECUTE_MODE="true"
fi

python3 - <<'PY'
import os
from sqlalchemy import create_engine, text

raw_url = os.environ["DATABASE_URL"]
source = os.environ["SOURCE_SCHEMA"]
target = os.environ["TARGET_SCHEMA"]
execute_mode = os.environ["EXECUTE_MODE"].lower() == "true"

if raw_url.startswith("postgres://"):
    url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
elif raw_url.startswith("postgresql://"):
    url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    url = raw_url

version_table = "alembic_version_amlredflags_v2"
# Keep amlredflags strictly ingestion-scoped: only these core tables plus its alembic version table.
aml_tables = [
    "batch_runs",
    "source_documents",
    "red_flags",
    version_table,
]

engine = create_engine(url)

print(f"Schema migration plan: {source} -> {target}")
print(f"Mode: {'EXECUTE' if execute_mode else 'DRY RUN'}")

with engine.begin() as conn:
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{target}"'))

    existing_rows = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
            """
        ),
        {"schema": source},
    ).fetchall()
    existing = {r[0] for r in existing_rows}

    to_move = [t for t in aml_tables if t in existing]
    skipped = [t for t in aml_tables if t not in existing]

    if not to_move:
        print("No amlredflags tables found in source schema. Nothing to move.")
        raise SystemExit(0)

    print("Tables to move:")
    for t in to_move:
        print(f"  - {source}.{t} -> {target}.{t}")

    if skipped:
        print("Tables not found in source schema (skipped):")
        for t in skipped:
            print(f"  - {source}.{t}")

    if not execute_mode:
        print("\nDry run complete. Re-run with --execute to perform migration.")
        raise SystemExit(0)

    for t in to_move:
        conn.execute(text(f'ALTER TABLE "{source}"."{t}" SET SCHEMA "{target}"'))

print("\nSchema migration complete.")
print("Next steps:")
print(f"1) Set DB_SCHEMA={target} in amlredflags environment.")
print("2) Run ./scripts/migrate_db.sh remote upgrade (or local upgrade) to verify Alembic state.")
PY
