#!/bin/bash
# Check AML Red Flags v2 batch status.
# Usage: ./scripts/check_batch.sh [api-base-url|remote]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ "$API_BASE_URL" = "remote" ]; then
  if [ -z "${AMLREDFLAGS_URL:-}" ]; then
    echo -e "${RED}Error: AMLREDFLAGS_URL is not set.${NC}"
    echo "Set it first, for example:"
    echo "  export AMLREDFLAGS_URL=\"https://amlredflags-f7faf72ea2f9.herokuapp.com\""
    exit 1
  fi
  API_BASE_URL="$AMLREDFLAGS_URL"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AML Red Flags v2 - Batch Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo "API base URL: $API_BASE_URL"
echo ""

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}Error: curl is required.${NC}"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}Error: jq is required.${NC}"
  exit 1
fi

STATUS_RESPONSE="$(curl -sS "$API_BASE_URL/api/batch/status" || true)"
HEALTH_RESPONSE="$(curl -sS "$API_BASE_URL/api/health" || true)"

STATUS_OK="$(echo "$STATUS_RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"
HEALTH_OK="$(echo "$HEALTH_RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"

if [ "$STATUS_OK" != "true" ]; then
  DETAIL="$(echo "$STATUS_RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
  echo -e "${RED}Status endpoint failed: $DETAIL${NC}"
  exit 1
fi

RUNNING="$(echo "$STATUS_RESPONSE" | jq -r '.running')"
LAST_BATCH_ID="$(echo "$STATUS_RESPONSE" | jq -r '.last_batch_id // "N/A"')"
LAST_STATUS="$(echo "$STATUS_RESPONSE" | jq -r '.last_status // "N/A"')"
STARTED_AT="$(echo "$STATUS_RESPONSE" | jq -r '.started_at // "N/A"')"
ENDED_AT="$(echo "$STATUS_RESPONSE" | jq -r '.ended_at // "N/A"')"
LAST_FAILURE_REASON="$(echo "$STATUS_RESPONSE" | jq -r '.last_failure_reason // empty')"
LAST_BATCH_RED_FLAGS_ADDED="$(echo "$STATUS_RESPONSE" | jq -r '.last_batch_red_flags_added // 0')"
LAST_BATCH_UNIQUE_SOURCES_ADDED="$(echo "$STATUS_RESPONSE" | jq -r '.last_batch_unique_sources_added // 0')"

echo -e "${BLUE}Current Batch State:${NC}"
if [ "$RUNNING" = "true" ]; then
  echo -e "  Running: ${YELLOW}true${NC}"
else
  echo -e "  Running: ${GREEN}false${NC}"
fi
echo "  Last Batch ID: $LAST_BATCH_ID"
echo "  Last Status: $LAST_STATUS"
echo "  Started At: $STARTED_AT"
echo "  Ended At: $ENDED_AT"
if [ -n "$LAST_FAILURE_REASON" ]; then
  echo -e "  Last Failure Reason: ${RED}$LAST_FAILURE_REASON${NC}"
fi
echo "  Last Batch Red Flags Added: $LAST_BATCH_RED_FLAGS_ADDED"
echo "  Last Batch Unique Sources Added: $LAST_BATCH_UNIQUE_SOURCES_ADDED"

echo ""
echo -e "${BLUE}Service Health:${NC}"
if [ "$HEALTH_OK" = "true" ]; then
  HEALTH_STATUS="$(echo "$HEALTH_RESPONSE" | jq -r '.status')"
  HEALTH_FLAGS="$(echo "$HEALTH_RESPONSE" | jq -r '.red_flags_count // 0')"
  TOTAL_SOURCES="$(echo "$HEALTH_RESPONSE" | jq -r '.unique_sources_count // 0')"
  TOTAL_DOCUMENTS="$(echo "$HEALTH_RESPONSE" | jq -r '.total_documents_count // 0')"
  TOTAL_BATCHES="$(echo "$HEALTH_RESPONSE" | jq -r '.total_batches_processed // 0')"
  HEALTH_LAST_BATCH_ID="$(echo "$HEALTH_RESPONSE" | jq -r '.last_batch_id // "N/A"')"
  HEALTH_LAST_BATCH_STATUS="$(echo "$HEALTH_RESPONSE" | jq -r '.last_batch_status // "N/A"')"
  HEALTH_LAST_FAILURE_REASON="$(echo "$HEALTH_RESPONSE" | jq -r '.last_batch_failure_reason // empty')"
  echo -e "  API Health: ${GREEN}$HEALTH_STATUS${NC}"
  echo "  Stored Red Flags: $HEALTH_FLAGS"
  echo "  Total Source Feeds: $TOTAL_SOURCES"
  echo "  Total Documents (Articles): $TOTAL_DOCUMENTS"
  echo "  Total Batches Processed: $TOTAL_BATCHES"
  echo "  Last Batch ID: $HEALTH_LAST_BATCH_ID"
  echo "  Last Batch Status: $HEALTH_LAST_BATCH_STATUS"
  if [ -n "$HEALTH_LAST_FAILURE_REASON" ]; then
    echo -e "  Last Batch Failure Reason: ${RED}$HEALTH_LAST_FAILURE_REASON${NC}"
  fi
else
  HEALTH_DETAIL="$(echo "$HEALTH_RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
  echo -e "  API Health: ${RED}unhealthy${NC}"
  echo "  Detail: $HEALTH_DETAIL"
fi

echo ""
echo -e "${BLUE}Quick Actions:${NC}"
echo "  Trigger: ./scripts/trigger_batch.sh $API_BASE_URL"
echo "  Monitor: ./scripts/trigger_batch.sh $API_BASE_URL --monitor"
echo "  Wait:    ./scripts/trigger_batch.sh $API_BASE_URL --wait"
echo "  Reset:   ./scripts/reset_db.sh $API_BASE_URL"
echo "  Health:  ./scripts/check_health.sh $API_BASE_URL"
echo "  Catalog: ./scripts/check_catalog.sh $API_BASE_URL"
