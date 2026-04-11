from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.database import SessionLocal
from app.models import AppUser, PlatformUserRole, Role, Tenant, TenantModuleEntitlement, TenantUser, TenantUserRole


@dataclass
class AuthContext:
    user_id: int | None = None
    email: str | None = None
    tenant_id: int | None = None
    platform_roles: set[str] = field(default_factory=set)
    tenant_roles: set[str] = field(default_factory=set)
    resolution_error: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_platform_admin(self) -> bool:
        return "application_admin" in self.platform_roles


def _resolve_auth_context(request: Request, db: Session) -> AuthContext:
    ctx = AuthContext()
    user_email = (request.headers.get("x-user-email") or "").strip().lower()
    tenant_raw = (request.headers.get("x-tenant-id") or "").strip()

    if not user_email and not tenant_raw:
        return ctx

    if tenant_raw and not user_email:
        ctx.resolution_error = "x-user-email is required when x-tenant-id is provided"
        return ctx

    if user_email:
        user = db.query(AppUser).filter(AppUser.email == user_email, AppUser.status == "active").first()
        if user is None:
            ctx.resolution_error = "User not found or inactive"
            return ctx
        ctx.user_id = user.id
        ctx.email = user.email

        platform_roles = (
            db.query(Role.code)
            .join(PlatformUserRole, PlatformUserRole.role_id == Role.id)
            .filter(PlatformUserRole.app_user_id == user.id)
            .all()
        )
        ctx.platform_roles = {row[0] for row in platform_roles}

    if tenant_raw:
        try:
            tenant_id = int(tenant_raw)
        except ValueError:
            ctx.resolution_error = "x-tenant-id must be an integer"
            return ctx

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.status == "active").first()
        if tenant is None:
            ctx.resolution_error = "Tenant not found or inactive"
            return ctx

        tenant_user = (
            db.query(TenantUser)
            .filter(
                TenantUser.tenant_id == tenant_id,
                TenantUser.app_user_id == ctx.user_id,
                TenantUser.status == "active",
            )
            .first()
        )
        if tenant_user is None and not ctx.is_platform_admin:
            ctx.resolution_error = "User is not an active member of tenant"
            return ctx

        ctx.tenant_id = tenant_id
        if tenant_user is not None:
            tenant_roles = (
                db.query(Role.code)
                .join(TenantUserRole, TenantUserRole.role_id == Role.id)
                .filter(TenantUserRole.tenant_user_id == tenant_user.id)
                .all()
            )
            ctx.tenant_roles = {row[0] for row in tenant_roles}

    return ctx


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        db = SessionLocal()
        try:
            request.state.auth_context = _resolve_auth_context(request, db)
        finally:
            db.close()
        return await call_next(request)


def get_auth_context(request: Request) -> AuthContext:
    return getattr(request.state, "auth_context", AuthContext())


def require_authenticated_user(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if auth.resolution_error:
        raise HTTPException(status_code=401, detail=auth.resolution_error)
    if not auth.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


def require_platform_admin(auth: AuthContext = Depends(require_authenticated_user)) -> AuthContext:
    if not auth.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin role required")
    return auth


def require_tenant_context(*required_roles: str):
    def _dependency(auth: AuthContext = Depends(require_authenticated_user)) -> AuthContext:
        if auth.tenant_id is None:
            raise HTTPException(status_code=403, detail="Tenant context required")

        if auth.is_platform_admin:
            return auth

        if required_roles:
            if not any(role in auth.tenant_roles for role in required_roles):
                raise HTTPException(
                    status_code=403,
                    detail=f"Tenant role required: one of {', '.join(required_roles)}",
                )
        return auth

    return _dependency


def _tenant_has_active_entitlement(db: Session, tenant_id: int, module_code: str) -> bool:
    now = datetime.now(timezone.utc)
    entitlement = (
        db.query(TenantModuleEntitlement)
        .filter(
            TenantModuleEntitlement.tenant_id == tenant_id,
            TenantModuleEntitlement.module_code == module_code,
            TenantModuleEntitlement.status == "active",
            or_(TenantModuleEntitlement.enabled_from.is_(None), TenantModuleEntitlement.enabled_from <= now),
            or_(TenantModuleEntitlement.enabled_to.is_(None), TenantModuleEntitlement.enabled_to >= now),
        )
        .first()
    )
    return entitlement is not None


def require_tenant_permission(module_code: str, *required_roles: str):
    def _dependency(auth: AuthContext = Depends(require_tenant_context())) -> AuthContext:
        if auth.is_platform_admin:
            return auth

        if auth.tenant_id is None:
            raise HTTPException(status_code=403, detail="Tenant context required")

        db = SessionLocal()
        try:
            if not _tenant_has_active_entitlement(db, auth.tenant_id, module_code):
                raise HTTPException(status_code=403, detail=f"Tenant lacks active module entitlement: {module_code}")
        finally:
            db.close()

        if required_roles and not any(role in auth.tenant_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Tenant role required for {module_code}: one of {', '.join(required_roles)}",
            )
        return auth

    return _dependency
