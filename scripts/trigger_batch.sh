#!/bin/bash
# Trigger AML Red Flags v2 batch processing.
# Usage: ./scripts/trigger_batch.sh [api-base-url|remote] [--monitor|--wait]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8001}"
MODE="${2:-}"

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
echo -e "${BLUE}AML Red Flags v2 - Trigger Batch${NC}"
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

RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/batch/trigger" || true)"
SUCCESS="$(echo "$RESPONSE" | jq -r '.success // false' 2>/dev/null || echo "false")"

if [ "$SUCCESS" = "true" ]; then
  BATCH_ID="$(echo "$RESPONSE" | jq -r '.batch_id')"
  MESSAGE="$(echo "$RESPONSE" | jq -r '.message')"
  echo -e "${GREEN}Batch accepted.${NC}"
  echo "Message: $MESSAGE"
  echo "Batch ID: $BATCH_ID"
else
  DETAIL="$(echo "$RESPONSE" | jq -r '.detail // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")"
  echo -e "${RED}Batch trigger failed: $DETAIL${NC}"
  exit 1
fi

if [ "$MODE" = "--monitor" ] || [ "$MODE" = "--wait" ]; then
  echo ""
  echo "Waiting for completion..."
  ELAPSED=0
  INTERVAL=2
  MAX_WAIT=900

  while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
    STATUS="$(curl -sS "$API_BASE_URL/api/batch/status" || true)"
    RUNNING="$(echo "$STATUS" | jq -r '.running // false' 2>/dev/null || echo "false")"
    LAST_STATUS="$(echo "$STATUS" | jq -r '.last_status // "unknown"' 2>/dev/null || echo "unknown")"
    LAST_BATCH_ID="$(echo "$STATUS" | jq -r '.last_batch_id // "n/a"' 2>/dev/null || echo "n/a")"
    LAST_FAILURE_REASON="$(echo "$STATUS" | jq -r '.last_failure_reason // empty' 2>/dev/null || echo "")"

    if [ "$RUNNING" = "true" ]; then
      if [ "$MODE" = "--monitor" ]; then
        echo -e "${YELLOW}Running...${NC} batch=$LAST_BATCH_ID status=$LAST_STATUS elapsed=${ELAPSED}s"
      fi
    else
      if [ "$LAST_STATUS" = "failed" ]; then
        echo -e "${RED}Complete with failure.${NC} batch=$LAST_BATCH_ID status=$LAST_STATUS"
        if [ -n "$LAST_FAILURE_REASON" ]; then
          echo "Reason: $LAST_FAILURE_REASON"
        fi
        exit 1
      fi
      echo -e "${GREEN}Complete.${NC} batch=$LAST_BATCH_ID status=$LAST_STATUS"
      exit 0
    fi

    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
  done

  echo -e "${RED}Timed out after ${MAX_WAIT}s waiting for batch completion.${NC}"
  exit 1
fi

echo ""
echo "Monitor: ./scripts/trigger_batch.sh $API_BASE_URL --monitor"
echo "Wait:    ./scripts/trigger_batch.sh $API_BASE_URL --wait"
