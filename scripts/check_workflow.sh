#!/bin/bash
# Workflow helper for template/active/draft lifecycle API calls.
#
# Usage:
#   ./scripts/check_workflow.sh [api-base-url|remote] templates
#   ./scripts/check_workflow.sh [api-base-url|remote] active <module_code> <entity_type>
#   ./scripts/check_workflow.sh [api-base-url|remote] create-draft <module_code> <entity_type> [name]
#   ./scripts/check_workflow.sh [api-base-url|remote] validate <module_code> <entity_type> <version_id>
#   ./scripts/check_workflow.sh [api-base-url|remote] publish <module_code> <entity_type> <version_id> [publish_comment]
#   ./scripts/check_workflow.sh [api-base-url|remote] update-draft <module_code> <entity_type> <payload_json_file>
#   ./scripts/check_workflow.sh [api-base-url|remote] rollback <module_code> <entity_type> <target_workflow_version_id> [reason]

set -euo pipefail

API_BASE_URL="${1:-http://localhost:8000}"
COMMAND="${2:-}"
MODULE_CODE="${3:-}"
ENTITY_TYPE="${4:-}"
ARG5="${5:-}"
ARG6="${6:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

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
      AMLINSIGHTS_URL)
        if [ -z "${AMLINSIGHTS_URL:-}" ]; then AMLINSIGHTS_URL="$value"; fi
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
  if [ -z "${AMLINSIGHTS_URL:-}" ]; then
    echo -e "${RED}Error: AMLINSIGHTS_URL is not set (point this to amlInsights).${NC}"
    exit 1
  fi
  API_BASE_URL="$AMLINSIGHTS_URL"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}Error: curl is required.${NC}"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo -e "${RED}Error: jq is required.${NC}"
  exit 1
fi

if [ -z "$COMMAND" ]; then
  echo -e "${RED}Error: command is required.${NC}"
  exit 1
fi

if [ -z "${AML_USER_EMAIL:-}" ]; then
  echo -e "${RED}Error: AML_USER_EMAIL is not set.${NC}"
  exit 1
fi

COMMON_HEADERS=(-H "x-user-email: $AML_USER_EMAIL")

if [ "$COMMAND" != "templates" ]; then
  if [ -z "${AML_TENANT_ID:-}" ]; then
    echo -e "${RED}Error: AML_TENANT_ID is not set.${NC}"
    exit 1
  fi
  COMMON_HEADERS+=(-H "x-tenant-id: $AML_TENANT_ID")
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AML Insights - Workflow Helper${NC}"
echo -e "${BLUE}========================================${NC}"
echo "API base URL: $API_BASE_URL"
echo "Command: $COMMAND"
echo "User: $AML_USER_EMAIL"
if [ "${AML_TENANT_ID:-}" != "" ]; then
  echo "Tenant ID: $AML_TENANT_ID"
fi
echo ""

case "$COMMAND" in
  templates)
    RESPONSE="$(curl -sS "$API_BASE_URL/api/platform/admin/workflow-templates" "${COMMON_HEADERS[@]}" || true)"
    ;;
  active)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ]; then
      echo -e "${RED}Usage: ... active <module_code> <entity_type>${NC}"
      exit 1
    fi
    RESPONSE="$(curl -sS "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE" "${COMMON_HEADERS[@]}" || true)"
    ;;
  create-draft)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ]; then
      echo -e "${RED}Usage: ... create-draft <module_code> <entity_type> [name]${NC}"
      exit 1
    fi
    DRAFT_NAME="${ARG5:-Tenant Draft}"
    PAYLOAD="$(jq -n --arg name "$DRAFT_NAME" '{name:$name, clone_from:{source:"system_template"}}')"
    RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE/draft" "${COMMON_HEADERS[@]}" -H "Content-Type: application/json" -d "$PAYLOAD" || true)"
    ;;
  validate)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ] || [ -z "$ARG5" ]; then
      echo -e "${RED}Usage: ... validate <module_code> <entity_type> <version_id>${NC}"
      exit 1
    fi
    PAYLOAD="$(jq -n --argjson version_id "$ARG5" '{version_id:$version_id}')"
    RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE/draft/validate" "${COMMON_HEADERS[@]}" -H "Content-Type: application/json" -d "$PAYLOAD" || true)"
    ;;
  publish)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ] || [ -z "$ARG5" ]; then
      echo -e "${RED}Usage: ... publish <module_code> <entity_type> <version_id> [publish_comment]${NC}"
      exit 1
    fi
    COMMENT="${ARG6:-Published via check_workflow.sh}"
    PAYLOAD="$(jq -n --argjson version_id "$ARG5" --arg comment "$COMMENT" '{version_id:$version_id, publish_comment:$comment}')"
    RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE/draft/publish" "${COMMON_HEADERS[@]}" -H "Content-Type: application/json" -d "$PAYLOAD" || true)"
    ;;

  update-draft)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ] || [ -z "$ARG5" ]; then
      echo -e "${RED}Usage: ... update-draft <module_code> <entity_type> <payload_json_file>${NC}"
      exit 1
    fi
    if [ ! -f "$ARG5" ]; then
      echo -e "${RED}Error: payload file not found: $ARG5${NC}"
      exit 1
    fi
    PAYLOAD="$(cat "$ARG5")"
    RESPONSE="$(curl -sS -X PATCH "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE/draft" "${COMMON_HEADERS[@]}" -H "Content-Type: application/json" -d "$PAYLOAD" || true)"
    ;;
  rollback)
    if [ -z "$MODULE_CODE" ] || [ -z "$ENTITY_TYPE" ] || [ -z "$ARG5" ]; then
      echo -e "${RED}Usage: ... rollback <module_code> <entity_type> <target_workflow_version_id> [reason]${NC}"
      exit 1
    fi
    REASON="${ARG6:-Rolled back via check_workflow.sh}"
    PAYLOAD="$(jq -n --argjson target_workflow_version_id "$ARG5" --arg reason "$REASON" '{target_workflow_version_id:$target_workflow_version_id, reason:$reason}')"
    RESPONSE="$(curl -sS -X POST "$API_BASE_URL/api/platform/workflows/$MODULE_CODE/$ENTITY_TYPE/draft/rollback" "${COMMON_HEADERS[@]}" -H "Content-Type: application/json" -d "$PAYLOAD" || true)"
    ;;
  *)
    echo -e "${RED}Unknown command: $COMMAND${NC}"
    exit 1
    ;;
esac

echo "$RESPONSE" | jq .
