#!/bin/bash
# Check AML Red Flags v2 batch status.
# Usage: ./scripts/check_batch.sh [api-base-url]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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
echo "  Last Batch Red Flags Added: $LAST_BATCH_RED_FLAGS_ADDED"
echo "  Last Batch Unique Sources Added: $LAST_BATCH_UNIQUE_SOURCES_ADDED"

echo ""
echo -e "${BLUE}Service Health:${NC}"
if [ "$HEALTH_OK" = "true" ]; then
  HEALTH_STATUS="$(echo "$HEALTH_RESPONSE" | jq -r '.status')"
  HEALTH_FLAGS="$(echo "$HEALTH_RESPONSE" | jq -r '.red_flags_count // 0')"
  TOTAL_SOURCES="$(echo "$HEALTH_RESPONSE" | jq -r '.unique_sources_count // 0')"
  TOTAL_BATCHES="$(echo "$HEALTH_RESPONSE" | jq -r '.total_batches_processed // 0')"
  echo -e "  API Health: ${GREEN}$HEALTH_STATUS${NC}"
  echo "  Stored Red Flags: $HEALTH_FLAGS"
  echo "  Total Sources: $TOTAL_SOURCES"
  echo "  Total Batches Processed: $TOTAL_BATCHES"
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
