from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.auth import AuthContext
from app.database import SessionLocal
from app.models import APIUsageEvent


def _infer_module_code(path: str) -> str | None:
    if path.startswith("/api/red-flags"):
        return "red_flags"
    if path.startswith("/api/tm") or path.startswith("/api/transaction-monitoring"):
        return "transaction_monitoring"
    if path.startswith("/api/reports"):
        return "operational_reporting"
    return None


class APIUsageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        auth: AuthContext = getattr(request.state, "auth_context", AuthContext())
        module_code = _infer_module_code(request.url.path)
        tenant_id = auth.tenant_id if auth.is_authenticated else None

        db = SessionLocal()
        try:
            db.add(
                APIUsageEvent(
                    tenant_id=tenant_id,
                    module_code=module_code,
                    endpoint=request.url.path[:255],
                    method=request.method[:16],
                    status_code=response.status_code,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return response
