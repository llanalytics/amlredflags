#!/bin/bash
# Check shared red flags catalog API.
# Usage: ./scripts/check_catalog.sh [api-base-url|remote] [limit] [offset]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"
LIMIT="${2:-10}"
OFFSET="${3:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Load only needed keys from .env if not already exported.
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
      AMLREDFLAGS_URL)
        if [ -z "${AMLREDFLAGS_URL:-}" ]; then AMLREDFLAGS_URL="$value"; fi
        ;;
      AML_USER_EMAIL)
        if [ -z "${AML_USER_EMAIL:-}" ]; then AML_USER_EMAIL="$value"; fi
        ;;
      AML_TENANT_ID)
        if [ -z "${AML_TENANT_ID:-}" ]; then AML_TENANT_ID="$value"; fi
        ;;
    esac
  done < "$ENV_FILE"
fi

if [ "$API_BASE_URL" = "remote" ]; then
  if [ -z "${AMLREDFLAGS_URL:-}" ]; then
    echo -e "${RED}Error: AMLREDFLAGS_URL is not set.${NC}"
    exit 1
  fi
  API_BASE_URL="$AMLREDFLAGS_URL"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}Error: curl is required.${NC}"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}Error: jq is required.${NC}"
  exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AML Red Flags v2 - Catalog Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo "API base URL: $API_BASE_URL"
echo "Limit: $LIMIT  Offset: $OFFSET"
if [ -n "${AML_USER_EMAIL:-}" ] && [ -n "${AML_TENANT_ID:-}" ]; then
  echo "Headers: x-user-email=$AML_USER_EMAIL  x-tenant-id=$AML_TENANT_ID"
else
  echo "Headers: none (public catalog mode)"
fi
echo ""

CURL_ARGS=(
  -sS
  "$API_BASE_URL/api/red-flags/catalog?limit=$LIMIT&offset=$OFFSET"
)

if [ -n "${AML_USER_EMAIL:-}" ] && [ -n "${AML_TENANT_ID:-}" ]; then
  CURL_ARGS+=( -H "x-user-email: $AML_USER_EMAIL" )
  CURL_ARGS+=( -H "x-tenant-id: $AML_TENANT_ID" )
fi

RESPONSE="$(curl "${CURL_ARGS[@]}" || true)"

SUCCESS="$(echo "$RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"
if [ "$SUCCESS" != "true" ]; then
  DETAIL="$(echo "$RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
  echo -e "${RED}Catalog request failed: $DETAIL${NC}"
  exit 1
fi

TOTAL="$(echo "$RESPONSE" | jq -r '.total // 0')"
COUNT="$(echo "$RESPONSE" | jq -r '.data | length')"
echo -e "${GREEN}Catalog request succeeded.${NC}"
echo "Total matching rows: $TOTAL"
echo "Rows returned: $COUNT"
echo ""
echo "$RESPONSE" | jq '.data[] | {id, source_name, category, severity, product_tags, service_tags, source_title}'
