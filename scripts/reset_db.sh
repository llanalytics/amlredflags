#!/bin/bash
# Reset AML Red Flags data and reseed bootstrap tables from amlInsights/install/*.csv
# Usage:
#   ./scripts/reset_db.sh [local|remote] [--yes]
#
# Behavior:
# - Empties batch tables: batch_runs, source_documents, red_flags
# - Upserts seed tables from CSV files in amlInsights/install/
#   required: roles.csv, red_flag_synonyms.csv
#   optional: tenants.csv, business_units.csv, tenant_module_entitlements.csv

set -euo pipefail

TARGET="${1:-local}"
CONFIRM_FLAG="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
SHARED_INSTALL_DIR="$(cd "$PROJECT_ROOT/../amlInsights/install" 2>/dev/null && pwd || true)"
LEGACY_INSTALL_DIR="$PROJECT_ROOT/install"
INSTALL_DIR="${AML_INSTALL_DIR:-$SHARED_INSTALL_DIR}"
if [ -z "$INSTALL_DIR" ] || [ ! -d "$INSTALL_DIR" ]; then
  INSTALL_DIR="$LEGACY_INSTALL_DIR"
fi

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Safe env loader (no source)
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac
    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    value="${value%$'\r'}"
    value="${value#\"}"
    value="${value%\"}"

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

if [ "$TARGET" != "local" ] && [ "$TARGET" != "remote" ]; then
  echo -e "${RED}Error: first argument must be 'local' or 'remote'.${NC}"
  exit 1
fi

if [ "$TARGET" = "local" ]; then
  DB_URL="${LOCAL_DATABASE_URL:-${DATABASE_URL:-}}"
else
  DB_URL="${DATABASE_URL:-}"
fi

if [ -z "$DB_URL" ]; then
  echo -e "${RED}Error: database URL not found for target '$TARGET'.${NC}"
  exit 1
fi

ROLES_CSV="$INSTALL_DIR/roles.csv"
SYNONYMS_CSV="$INSTALL_DIR/red_flag_synonyms.csv"
TENANTS_CSV="$INSTALL_DIR/tenants.csv"
BUSINESS_UNITS_CSV="$INSTALL_DIR/business_units.csv"
ENTITLEMENTS_CSV="$INSTALL_DIR/tenant_module_entitlements.csv"

if [ ! -f "$ROLES_CSV" ]; then
  echo -e "${RED}Error: missing $ROLES_CSV${NC}"
  exit 1
fi
if [ ! -f "$SYNONYMS_CSV" ]; then
  echo -e "${RED}Error: missing $SYNONYMS_CSV${NC}"
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo -e "${RED}Error: python is required.${NC}"
  exit 1
fi

if [ "$CONFIRM_FLAG" != "--yes" ]; then
  echo -e "${BLUE}Target:${NC} $TARGET"
  echo -e "${BLUE}Database:${NC} $DB_URL"
  echo -e "${BLUE}Schema:${NC} ${DB_SCHEMA:-<none>}"
  echo -e "${BLUE}Will clear:${NC} batch_runs, source_documents, red_flags"
  echo -e "${BLUE}Will seed:${NC} roles, red_flag_synonyms"
  [ -f "$TENANTS_CSV" ] && echo -e "${BLUE}Optional seed:${NC} tenants"
  [ -f "$BUSINESS_UNITS_CSV" ] && echo -e "${BLUE}Optional seed:${NC} business_units"
  [ -f "$ENTITLEMENTS_CSV" ] && echo -e "${BLUE}Optional seed:${NC} tenant_module_entitlements"
  read -r -p "Type 'yes' to continue: " CONFIRM
  if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 1
  fi
fi

DB_URL="$DB_URL" DB_SCHEMA="${DB_SCHEMA:-}" \
ROLES_CSV="$ROLES_CSV" SYNONYMS_CSV="$SYNONYMS_CSV" \
TENANTS_CSV="$TENANTS_CSV" BUSINESS_UNITS_CSV="$BUSINESS_UNITS_CSV" ENTITLEMENTS_CSV="$ENTITLEMENTS_CSV" \
python - <<'PY'
import csv
import os
import re
from datetime import datetime, timezone

from sqlalchemy import MetaData, Table, and_, create_engine, func, select


def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def norm_key(value: str) -> str:
    s = (value or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def file_exists(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def parse_ts(raw: str | None):
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def log(msg: str):
    print(msg)


db_url = normalize_db_url(os.environ["DB_URL"])
db_schema = (os.environ.get("DB_SCHEMA") or "").strip() or None
roles_csv = os.environ["ROLES_CSV"]
synonyms_csv = os.environ["SYNONYMS_CSV"]
tenants_csv = os.environ.get("TENANTS_CSV", "")
business_units_csv = os.environ.get("BUSINESS_UNITS_CSV", "")
entitlements_csv = os.environ.get("ENTITLEMENTS_CSV", "")

engine = create_engine(db_url)
metadata = MetaData(schema=db_schema)

with engine.begin() as conn:
    batch_runs = Table("batch_runs", metadata, autoload_with=conn)
    source_documents = Table("source_documents", metadata, autoload_with=conn)
    red_flags = Table("red_flags", metadata, autoload_with=conn)
    roles = Table("roles", metadata, autoload_with=conn)
    red_flag_synonyms = Table("red_flag_synonyms", metadata, autoload_with=conn)

    tenants = None
    business_units = None
    tenant_module_entitlements = None
    try:
        tenants = Table("tenants", metadata, autoload_with=conn)
    except Exception:
        pass
    try:
        business_units = Table("business_units", metadata, autoload_with=conn)
    except Exception:
        pass
    try:
        tenant_module_entitlements = Table("tenant_module_entitlements", metadata, autoload_with=conn)
    except Exception:
        pass

    # 1) Clear batch tables in FK-safe order.
    deleted_rf = conn.execute(red_flags.delete()).rowcount or 0
    deleted_docs = conn.execute(source_documents.delete()).rowcount or 0
    deleted_batches = conn.execute(batch_runs.delete()).rowcount or 0
    log(f"Cleared red_flags={deleted_rf}, source_documents={deleted_docs}, batch_runs={deleted_batches}")

    now = datetime.now(timezone.utc)

    # 2) Upsert roles (required)
    role_ins = role_upd = 0
    with open(roles_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip()
            scope = (row.get("scope") or "tenant").strip()
            description = (row.get("description") or "").strip() or None
            if not code:
                continue

            existing = conn.execute(
                select(roles.c.id).where(func.lower(roles.c.code) == code.lower())
            ).first()

            if existing:
                conn.execute(
                    roles.update().where(roles.c.id == int(existing.id)).values(scope=scope, description=description)
                )
                role_upd += 1
            else:
                payload = {"code": code, "scope": scope, "description": description}
                if "created_at" in roles.c:
                    payload["created_at"] = now
                conn.execute(roles.insert().values(**payload))
                role_ins += 1
    log(f"Seeded roles: inserted={role_ins}, updated={role_upd}")

    # 3) Upsert synonyms (required)
    syn_ins = syn_upd = 0
    with open(synonyms_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            scope = (row.get("scope") or "").strip().lower()
            raw_value = (row.get("raw_value") or "").strip()
            canonical_value = (row.get("canonical_value") or "").strip().lower().replace(" ", "_")
            raw_value_key = norm_key(raw_value)
            is_active_raw = (row.get("is_active") or "true").strip().lower()
            is_active = is_active_raw in {"1", "true", "yes", "y"}

            if scope not in {"category", "product", "service"}:
                continue
            if not raw_value or not raw_value_key or not canonical_value:
                continue

            existing = conn.execute(
                select(red_flag_synonyms.c.id).where(
                    and_(
                        red_flag_synonyms.c.scope == scope,
                        red_flag_synonyms.c.raw_value_key == raw_value_key,
                    )
                )
            ).first()

            values = {
                "scope": scope,
                "raw_value": raw_value,
                "raw_value_key": raw_value_key,
                "canonical_value": canonical_value,
                "is_active": is_active,
            }
            if "updated_at" in red_flag_synonyms.c:
                values["updated_at"] = now

            if existing:
                conn.execute(red_flag_synonyms.update().where(red_flag_synonyms.c.id == int(existing.id)).values(**values))
                syn_upd += 1
            else:
                if "created_at" in red_flag_synonyms.c:
                    values["created_at"] = now
                conn.execute(red_flag_synonyms.insert().values(**values))
                syn_ins += 1
    log(f"Seeded red_flag_synonyms: inserted={syn_ins}, updated={syn_upd}")

    tenant_name_to_id: dict[str, int] = {}

    # 4) Optional: tenants
    if file_exists(tenants_csv) and tenants is not None:
        ins = upd = 0
        with open(tenants_csv, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = " ".join((row.get("name") or "").split())
                status = (row.get("status") or "active").strip().lower() or "active"
                if not name:
                    continue
                existing = conn.execute(
                    select(tenants.c.id).where(func.lower(func.trim(tenants.c.name)) == name.lower())
                ).first()
                if existing:
                    conn.execute(
                        tenants.update().where(tenants.c.id == int(existing.id)).values(status=status, updated_at=now)
                    )
                    tenant_id = int(existing.id)
                    upd += 1
                else:
                    payload = {"name": name, "status": status}
                    if "created_at" in tenants.c:
                        payload["created_at"] = now
                    if "updated_at" in tenants.c:
                        payload["updated_at"] = now
                    result = conn.execute(tenants.insert().values(**payload))
                    tenant_id = int(result.inserted_primary_key[0])
                    ins += 1
                tenant_name_to_id[name.lower()] = tenant_id
        log(f"Seeded tenants: inserted={ins}, updated={upd}")
    else:
        if tenants is None:
            log("Skipped tenants seed: tenants table not found")

    # Refresh tenant map if table exists (used by downstream optional seeds)
    if tenants is not None and not tenant_name_to_id:
        for tid, tname in conn.execute(select(tenants.c.id, tenants.c.name)).all():
            tenant_name_to_id[str(tname).strip().lower()] = int(tid)

    # 5) Optional: business_units
    if file_exists(business_units_csv) and business_units is not None:
        ins = upd = skip = 0
        with open(business_units_csv, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                tenant_name = " ".join((row.get("tenant_name") or "").split()).lower()
                code = norm_key(row.get("code") or "")
                name = " ".join((row.get("name") or "").split())
                status = (row.get("status") or "active").strip().lower() or "active"
                tenant_id = tenant_name_to_id.get(tenant_name)
                if not tenant_id or not code or not name:
                    skip += 1
                    continue
                existing = conn.execute(
                    select(business_units.c.id).where(
                        and_(
                            business_units.c.tenant_id == tenant_id,
                            func.lower(func.trim(business_units.c.code)) == code.lower(),
                        )
                    )
                ).first()
                if existing:
                    conn.execute(
                        business_units.update().where(business_units.c.id == int(existing.id)).values(name=name, status=status, updated_at=now)
                    )
                    upd += 1
                else:
                    payload = {
                        "tenant_id": tenant_id,
                        "code": code,
                        "name": name,
                        "status": status,
                    }
                    if "created_at" in business_units.c:
                        payload["created_at"] = now
                    if "updated_at" in business_units.c:
                        payload["updated_at"] = now
                    conn.execute(business_units.insert().values(**payload))
                    ins += 1
        log(f"Seeded business_units: inserted={ins}, updated={upd}, skipped={skip}")
    else:
        if business_units is None:
            log("Skipped business_units seed: business_units table not found")

    # 6) Optional: tenant_module_entitlements
    if file_exists(entitlements_csv) and tenant_module_entitlements is not None:
        ins = upd = skip = 0
        with open(entitlements_csv, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                tenant_name = " ".join((row.get("tenant_name") or "").split()).lower()
                module_code = norm_key(row.get("module_code") or "")
                status = (row.get("status") or "active").strip().lower() or "active"
                enabled_from = parse_ts(row.get("enabled_from"))
                enabled_to = parse_ts(row.get("enabled_to"))
                tenant_id = tenant_name_to_id.get(tenant_name)
                if not tenant_id or not module_code:
                    skip += 1
                    continue

                existing = conn.execute(
                    select(tenant_module_entitlements.c.id).where(
                        and_(
                            tenant_module_entitlements.c.tenant_id == tenant_id,
                            tenant_module_entitlements.c.module_code == module_code,
                        )
                    )
                ).first()
                values = {
                    "status": status,
                    "enabled_from": enabled_from,
                    "enabled_to": enabled_to,
                }
                if existing:
                    conn.execute(
                        tenant_module_entitlements.update()
                        .where(tenant_module_entitlements.c.id == int(existing.id))
                        .values(**values)
                    )
                    upd += 1
                else:
                    payload = {
                        "tenant_id": tenant_id,
                        "module_code": module_code,
                        **values,
                    }
                    if "created_at" in tenant_module_entitlements.c:
                        payload["created_at"] = now
                    conn.execute(tenant_module_entitlements.insert().values(**payload))
                    ins += 1
        log(f"Seeded tenant_module_entitlements: inserted={ins}, updated={upd}, skipped={skip}")
    else:
        if tenant_module_entitlements is None:
            log("Skipped tenant_module_entitlements seed: tenant_module_entitlements table not found")

print("Reset + seed completed.")
PY

echo -e "${GREEN}Reset + seed completed successfully.${NC}"
