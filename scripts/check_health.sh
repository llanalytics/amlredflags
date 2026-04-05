#!/bin/bash
# Check AML Red Flags service health.
# Usage: ./scripts/check_health.sh [api-base-url|remote]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Load AMLREDFLAGS_URL from .env if available and not already exported.
if [ -f "$ENV_FILE" ] && [ -z "${AMLREDFLAGS_URL:-}" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue
        ;;
    esac
    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    if [ "$key" = "AMLREDFLAGS_URL" ]; then
      AMLREDFLAGS_URL="$value"
      break
    fi
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

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}Error: curl is required.${NC}"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}Error: jq is required.${NC}"
  exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AML Red Flags v2 - Service Health${NC}"
echo -e "${BLUE}========================================${NC}"
echo "API base URL: $API_BASE_URL"
echo ""

RESPONSE="$(curl -sS "$API_BASE_URL/api/health" || true)"
SUCCESS="$(echo "$RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"

if [ "$SUCCESS" != "true" ]; then
  DETAIL="$(echo "$RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
  echo -e "${RED}Health check failed: $DETAIL${NC}"
  exit 1
fi

HEALTH_STATUS="$(echo "$RESPONSE" | jq -r '.status // "unknown"')"
HEALTH_FLAGS="$(echo "$RESPONSE" | jq -r '.red_flags_count // 0')"
TOTAL_SOURCES="$(echo "$RESPONSE" | jq -r '.unique_sources_count // 0')"
TOTAL_DOCUMENTS="$(echo "$RESPONSE" | jq -r '.total_documents_count // 0')"
TOTAL_BATCHES="$(echo "$RESPONSE" | jq -r '.total_batches_processed // 0')"
LAST_BATCH_ID="$(echo "$RESPONSE" | jq -r '.last_batch_id // "N/A"')"
LAST_BATCH_STATUS="$(echo "$RESPONSE" | jq -r '.last_batch_status // "N/A"')"
LAST_FAILURE_REASON="$(echo "$RESPONSE" | jq -r '.last_batch_failure_reason // empty')"

echo -e "  API Health: ${GREEN}$HEALTH_STATUS${NC}"
echo "  Stored Red Flags: $HEALTH_FLAGS"
echo "  Total Source Feeds: $TOTAL_SOURCES"
echo "  Total Documents (Articles): $TOTAL_DOCUMENTS"
echo "  Total Batches Processed: $TOTAL_BATCHES"
echo "  Last Batch ID: $LAST_BATCH_ID"
echo "  Last Batch Status: $LAST_BATCH_STATUS"
if [ -n "$LAST_FAILURE_REASON" ]; then
  echo -e "  Last Batch Failure Reason: ${RED}$LAST_FAILURE_REASON${NC}"
fi
