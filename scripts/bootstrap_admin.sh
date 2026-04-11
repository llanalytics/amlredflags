#!/bin/bash
# Bootstrap local admin and tenant access for workflow/catalog scripts.
#
# Usage:
#   ./scripts/bootstrap_admin.sh [admin_email] [tenant_name] [tenant_code]
#
# Example:
#   ./scripts/bootstrap_admin.sh owner@amlinsights.local "Default Tenant" default

set -euo pipefail

ADMIN_EMAIL="${1:-owner@amlinsights.local}"
TENANT_NAME="${2:-Default Tenant}"
TENANT_CODE="${3:-default}"
export ADMIN_EMAIL TENANT_NAME TENANT_CODE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

python - <<'PY'
import os

from app.database import SessionLocal
from app.models import (
    AppUser,
    BusinessUnit,
    PlatformUserRole,
    Role,
    Tenant,
    TenantModuleEntitlement,
    TenantUser,
    TenantUserRole,
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
TENANT_NAME = os.environ.get("TENANT_NAME")
TENANT_CODE = os.environ.get("TENANT_CODE")

MODULE_CODES = ("red_flags", "transaction_monitoring")

db = SessionLocal()
try:
    user = db.query(AppUser).filter(AppUser.email == ADMIN_EMAIL).first()
    if user is None:
        user = AppUser(email=ADMIN_EMAIL, status="active")
        db.add(user)
        db.flush()

    tenant = db.query(Tenant).filter(Tenant.name == TENANT_NAME).first()
    if tenant is None:
        tenant = Tenant(name=TENANT_NAME, status="active")
        db.add(tenant)
        db.flush()

    tenant_user = (
        db.query(TenantUser)
        .filter(TenantUser.tenant_id == tenant.id, TenantUser.app_user_id == user.id)
        .first()
    )
    if tenant_user is None:
        tenant_user = TenantUser(tenant_id=tenant.id, app_user_id=user.id, status="active")
        db.add(tenant_user)
        db.flush()

    role_codes_needed = ("application_admin", "tenant_admin", "read_only_audit")
    roles = {r.code: r for r in db.query(Role).filter(Role.code.in_(role_codes_needed)).all()}
    missing_roles = [code for code in role_codes_needed if code not in roles]
    if missing_roles:
        raise RuntimeError(
            "Missing required roles: "
            + ", ".join(missing_roles)
            + ". Run ./scripts/seed_baseline.sh first."
        )

    # Platform admin link.
    if (
        db.query(PlatformUserRole)
        .filter(
            PlatformUserRole.app_user_id == user.id,
            PlatformUserRole.role_id == roles["application_admin"].id,
        )
        .first()
        is None
    ):
        db.add(
            PlatformUserRole(
                app_user_id=user.id,
                role_id=roles["application_admin"].id,
            )
        )

    # Tenant role links.
    for code in ("tenant_admin", "read_only_audit"):
        if (
            db.query(TenantUserRole)
            .filter(
                TenantUserRole.tenant_user_id == tenant_user.id,
                TenantUserRole.role_id == roles[code].id,
            )
            .first()
            is None
        ):
            db.add(
                TenantUserRole(
                    tenant_user_id=tenant_user.id,
                    role_id=roles[code].id,
                )
            )

    # Module entitlements.
    for module_code in MODULE_CODES:
        if (
            db.query(TenantModuleEntitlement)
            .filter(
                TenantModuleEntitlement.tenant_id == tenant.id,
                TenantModuleEntitlement.module_code == module_code,
            )
            .first()
            is None
        ):
            db.add(
                TenantModuleEntitlement(
                    tenant_id=tenant.id,
                    module_code=module_code,
                    status="active",
                )
            )

    # Default flat business unit.
    if (
        db.query(BusinessUnit)
        .filter(BusinessUnit.tenant_id == tenant.id, BusinessUnit.code == TENANT_CODE)
        .first()
        is None
    ):
        db.add(
            BusinessUnit(
                tenant_id=tenant.id,
                name=f"{TENANT_NAME} Business Unit",
                code=TENANT_CODE,
                status="active",
            )
        )

    db.commit()

    print("bootstrap_complete=true")
    print(f"admin_email={user.email}")
    print(f"tenant_id={tenant.id}")
    print(f"tenant_name={tenant.name}")
    print("modules_enabled=red_flags,transaction_monitoring")
    print("suggested_env_lines:")
    print(f"AML_USER_EMAIL={user.email}")
    print(f"AML_TENANT_ID={tenant.id}")
finally:
    db.close()
PY
