#!/usr/bin/env bash
# Usage:
#   ./scripts/start_server.sh [local|remote|database-url] [port]
#
# Examples:
#   ./scripts/start_server.sh
#   ./scripts/start_server.sh local 8000
#   ./scripts/start_server.sh remote 8000
#   ./scripts/start_server.sh sqlite:////tmp/amlredflags.db 8000
set -euo pipefail

TARGET="${1:-local}"
PORT="${2:-8001}"
HOST="${HOST:-127.0.0.1}"
APP_MODULE="${APP_MODULE:-app.main:app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
PATH="$PROJECT_ROOT/.venv/bin:$PATH"

load_env_file() {
  local file="$1"
  [ -f "$file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac

    local key="${line%%=*}"
    local value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    case "$key" in
      DATABASE_URL)
        [ -z "${DATABASE_URL:-}" ] && export DATABASE_URL="$value"
        ;;
      LOCAL_DATABASE_URL)
        [ -z "${LOCAL_DATABASE_URL:-}" ] && export LOCAL_DATABASE_URL="$value"
        ;;
      DB_SCHEMA)
        [ -z "${DB_SCHEMA:-}" ] && export DB_SCHEMA="$value"
        ;;
      SECRET_KEY)
        [ -z "${SECRET_KEY:-}" ] && export SECRET_KEY="$value"
        ;;
      ENABLE_HTTPS_REDIRECT)
        [ -z "${ENABLE_HTTPS_REDIRECT:-}" ] && export ENABLE_HTTPS_REDIRECT="$value"
        ;;
      SESSION_HTTPS_ONLY)
        [ -z "${SESSION_HTTPS_ONLY:-}" ] && export SESSION_HTTPS_ONLY="$value"
        ;;
    esac
  done < "$file"
}

resolve_sqlite_url() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf 'sqlite:///%s\n' "$path"
  else
    printf 'sqlite:///%s/%s\n' "$PROJECT_ROOT" "$path"
  fi
}

load_env_file "$ENV_FILE"

case "$TARGET" in
  local)
    if [ -n "${LOCAL_DATABASE_URL:-}" ]; then
      DB_URL="$LOCAL_DATABASE_URL"
    elif [ -n "${DATABASE_URL:-}" ] && [[ "${DATABASE_URL:-}" == sqlite* ]]; then
      DB_URL="$DATABASE_URL"
    else
      DB_URL="sqlite:///$PROJECT_ROOT/amlredflags_v2.db"
    fi
    ;;
  remote)
    DB_URL="${DATABASE_URL:-}"
    ;;
  *)
    if [[ "$TARGET" == *"://"* ]]; then
      DB_URL="$TARGET"
    else
      DB_URL="$(resolve_sqlite_url "$TARGET")"
    fi
    ;;
esac

if [ -z "${DB_URL:-}" ]; then
  echo "Could not resolve DATABASE_URL for target '$TARGET'."
  echo "Set DATABASE_URL/LOCAL_DATABASE_URL in .env, or pass a full database URL."
  exit 1
fi

export DATABASE_URL="$DB_URL"

if [ -z "${SECRET_KEY:-}" ]; then
  export SECRET_KEY="local-dev-secret-key"
fi

cat <<MSG
Starting amlredflags:
  TARGET=$TARGET
  DATABASE_URL=$DATABASE_URL
  DB_SCHEMA=${DB_SCHEMA:-public}
  HOST=$HOST
  PORT=$PORT
  APP_MODULE=$APP_MODULE
MSG

cd "$PROJECT_ROOT"
if [ -x "$PROJECT_ROOT/.venv/bin/uvicorn" ]; then
  exec "$PROJECT_ROOT/.venv/bin/uvicorn" "$APP_MODULE" --host "$HOST" --port "$PORT" --reload
fi

exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" --reload
