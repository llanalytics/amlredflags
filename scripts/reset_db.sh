#!/bin/bash
# Reset AML Red Flags tables via API.
# Usage: ./scripts/reset_db.sh [api-base-url|remote] [--yes]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"
CONFIRM_FLAG="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Load only needed keys from .env without shell-sourcing (safe with spaces in values).
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

    case "$key" in
      RESET_API_TOKEN)
        if [ -z "${RESET_API_TOKEN:-}" ]; then
          RESET_API_TOKEN="$value"
        fi
        ;;
      AMLREDFLAGS_URL)
        if [ -z "${AMLREDFLAGS_URL:-}" ]; then
          AMLREDFLAGS_URL="$value"
        fi
        ;;
    esac
  done < "$ENV_FILE"
fi

if [ "$API_BASE_URL" = "remote" ]; then
  if [ -z "${AMLREDFLAGS_URL:-}" ]; then
    echo -e "${RED}Error: AMLREDFLAGS_URL is not set.${NC}"
    echo "Set it first, for example:"
    echo "  export AMLREDFLAGS_URL=\"https://amlredflags-f7faf72ea2f9.herokuapp.com\""
    exit 1
  fi
  API_BASE_URL="$AMLREDFLAGS_URL"
fi

if [ -z "${RESET_API_TOKEN:-}" ]; then
  echo -e "${RED}Error: RESET_API_TOKEN is not set.${NC}"
  echo "Set it first, for example:"
  echo "  export RESET_API_TOKEN=\"your-reset-token\""
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}Error: curl is required.${NC}"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}Error: jq is required.${NC}"
  exit 1
fi

if [ "$CONFIRM_FLAG" != "--yes" ]; then
  echo -e "${BLUE}This will delete all AML Red Flags batch data at:${NC} $API_BASE_URL"
  read -r -p "Type 'yes' to continue: " CONFIRM
  if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 1
  fi
fi

RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/admin/reset" \
  -H "X-Reset-Token: $RESET_API_TOKEN" || true)"
SUCCESS="$(echo "$RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"

if [ "$SUCCESS" = "true" ]; then
  echo -e "${GREEN}Reset complete.${NC}"
  echo "Message: $(echo "$RESPONSE" | jq -r '.message')"
  echo "Deleted Red Flags: $(echo "$RESPONSE" | jq -r '.deleted_red_flags // 0')"
  echo "Deleted Source Documents: $(echo "$RESPONSE" | jq -r '.deleted_source_documents // 0')"
  echo "Deleted Batch Runs: $(echo "$RESPONSE" | jq -r '.deleted_batch_runs // 0')"
  exit 0
fi

DETAIL="$(echo "$RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
echo -e "${RED}Reset failed: $DETAIL${NC}"
exit 1
