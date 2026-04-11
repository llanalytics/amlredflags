from datetime import datetime, timezone
import json

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.exc import SQLAlchemyError

from app.batch import is_batch_running, queue_batch_run
from app.config import RESET_API_TOKEN
from app.database import SessionLocal
from app.models import BatchRun, RedFlag, SourceDocument
from app.schemas import (
    BatchStatusResponse,
    HealthResponse,
    RedFlagCatalogItem,
    RedFlagCatalogResponse,
    ResetResponse,
    TriggerBatchResponse,
)

app = FastAPI(title="AML Red Flags v2")


def _parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if str(v).strip()]
    except Exception:
        pass
    return []


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db = SessionLocal()
    try:
        count = db.query(RedFlag).count()
        unique_sources = db.query(SourceDocument.source_name).distinct().count()
        total_documents = db.query(SourceDocument).count()
        total_batches = db.query(BatchRun).count()
        latest = db.query(BatchRun).order_by(desc(BatchRun.id)).first()
        return HealthResponse(
            success=True,
            status="healthy",
            red_flags_count=count,
            unique_sources_count=unique_sources,
            total_documents_count=total_documents,
            total_batches_processed=total_batches,
            last_batch_id=latest.batch_id if latest else None,
            last_batch_status=latest.status if latest else None,
            last_batch_failure_reason=latest.failure_reason if latest else None,
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


@app.post("/api/batch/trigger", response_model=TriggerBatchResponse, status_code=202)
def trigger_batch() -> TriggerBatchResponse:
    started, message, batch_id = queue_batch_run()
    if not started or batch_id is None:
        raise HTTPException(status_code=409, detail=message)

    return TriggerBatchResponse(
        success=True,
        message=message,
        batch_id=batch_id,
    )


@app.get("/api/batch/status", response_model=BatchStatusResponse)
def batch_status() -> BatchStatusResponse:
    db = SessionLocal()
    try:
        latest = db.query(BatchRun).order_by(desc(BatchRun.id)).first()
        if not latest:
            return BatchStatusResponse(
                success=True,
                running=False,
                last_batch_id=None,
                last_status=None,
                started_at=None,
                ended_at=None,
                last_failure_reason=None,
                last_batch_red_flags_added=0,
                last_batch_unique_sources_added=0,
            )

        window_start = latest.started_at
        window_end = latest.ended_at or datetime.now(timezone.utc)
        if window_start is None:
            red_flags_added = 0
            unique_sources_added = 0
        else:
            added_docs_query = db.query(SourceDocument).filter(
                SourceDocument.batch_id == latest.batch_id,
                SourceDocument.created_at >= window_start,
                SourceDocument.created_at <= window_end,
            )

            red_flags_added = (
                db.query(RedFlag)
                .join(SourceDocument, RedFlag.document_id == SourceDocument.id)
                .filter(
                    SourceDocument.batch_id == latest.batch_id,
                    SourceDocument.created_at >= window_start,
                    SourceDocument.created_at <= window_end,
                )
                .count()
            )
            unique_sources_added = (
                added_docs_query.with_entities(SourceDocument.source_name)
                .distinct()
                .count()
            )

        return BatchStatusResponse(
            success=True,
            running=latest.status in {"queued", "running"},
            last_batch_id=latest.batch_id,
            last_status=latest.status,
            started_at=latest.started_at,
            ended_at=latest.ended_at,
            last_failure_reason=latest.failure_reason,
            last_batch_red_flags_added=red_flags_added,
            last_batch_unique_sources_added=unique_sources_added,
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


@app.get("/api/redflags")
def list_redflags(limit: int = 100) -> dict:
    db = SessionLocal()
    try:
        rows = db.query(RedFlag).order_by(desc(RedFlag.id)).limit(min(limit, 1000)).all()
        return {
            "success": True,
            "count": len(rows),
            "data": [
                {
                    "id": r.id,
                    "category": r.category,
                    "severity": r.severity,
                    "text": r.text,
                    "confidence_score": r.confidence_score,
                    "product_tags": _parse_tags(r.product_tags_json),
                    "service_tags": _parse_tags(r.service_tags_json),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


@app.get("/api/red-flags/catalog", response_model=RedFlagCatalogResponse)
def list_red_flags_catalog(
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    severity: str | None = None,
    source_name: str | None = None,
    q: str | None = None,
) -> RedFlagCatalogResponse:
    db = SessionLocal()
    try:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)

        query = (
            db.query(RedFlag, SourceDocument)
            .join(SourceDocument, RedFlag.document_id == SourceDocument.id)
        )

        if category:
            query = query.filter(RedFlag.category.ilike(f"%{category.strip()}%"))
        if severity:
            query = query.filter(RedFlag.severity.ilike(f"%{severity.strip()}%"))
        if source_name:
            query = query.filter(SourceDocument.source_name.ilike(f"%{source_name.strip()}%"))
        if q:
            pattern = f"%{q.strip()}%"
            query = query.filter(or_(RedFlag.text.ilike(pattern), SourceDocument.title.ilike(pattern)))

        total = query.count()
        rows = (
            query.order_by(desc(RedFlag.created_at), desc(RedFlag.id))
            .offset(safe_offset)
            .limit(safe_limit)
            .all()
        )

        items = [
            RedFlagCatalogItem(
                id=flag.id,
                source_name=doc.source_name,
                source_url=doc.url,
                source_title=doc.title,
                category=flag.category,
                severity=flag.severity,
                text=flag.text,
                confidence_score=flag.confidence_score,
                product_tags=_parse_tags(flag.product_tags_json),
                service_tags=_parse_tags(flag.service_tags_json),
                created_at=flag.created_at,
            )
            for flag, doc in rows
        ]

        return RedFlagCatalogResponse(
            success=True,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            data=items,
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


@app.get("/api/red-flags/catalog/{catalog_id}", response_model=RedFlagCatalogItem)
def get_red_flag_catalog_item(catalog_id: int) -> RedFlagCatalogItem:
    db = SessionLocal()
    try:
        row = (
            db.query(RedFlag, SourceDocument)
            .join(SourceDocument, RedFlag.document_id == SourceDocument.id)
            .filter(RedFlag.id == catalog_id)
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Catalog item not found")

        flag, doc = row
        return RedFlagCatalogItem(
            id=flag.id,
            source_name=doc.source_name,
            source_url=doc.url,
            source_title=doc.title,
            category=flag.category,
            severity=flag.severity,
            text=flag.text,
            confidence_score=flag.confidence_score,
            product_tags=_parse_tags(flag.product_tags_json),
            service_tags=_parse_tags(flag.service_tags_json),
            created_at=flag.created_at,
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


@app.post("/api/admin/reset", response_model=ResetResponse)
def reset_database(x_reset_token: str | None = Header(default=None)) -> ResetResponse:
    if not RESET_API_TOKEN:
        raise HTTPException(status_code=503, detail="RESET_API_TOKEN is not configured")
    if x_reset_token != RESET_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid reset token")
    if is_batch_running():
        raise HTTPException(status_code=409, detail="Cannot reset while a batch is running")

    db = SessionLocal()
    try:
        deleted_red_flags = db.query(RedFlag).delete(synchronize_session=False)
        deleted_source_documents = db.query(SourceDocument).delete(synchronize_session=False)
        deleted_batch_runs = db.query(BatchRun).delete(synchronize_session=False)
        db.commit()
        return ResetResponse(
            success=True,
            message="AML Red Flags tables reset successfully",
            deleted_red_flags=deleted_red_flags,
            deleted_source_documents=deleted_source_documents,
            deleted_batch_runs=deleted_batch_runs,
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()


PLATFORM_API_MIGRATION_MESSAGE = (
    "Platform workflow/RBAC/auth APIs moved to amlInsights under /api/platform/*; "
    "update your client base URL to the amlInsights service."
)


def _platform_api_moved() -> None:
    raise HTTPException(status_code=410, detail=PLATFORM_API_MIGRATION_MESSAGE)


@app.get("/api/auth/context")
def deprecated_auth_context() -> dict:
    _platform_api_moved()


@app.get("/api/tenant/context")
def deprecated_tenant_context() -> dict:
    _platform_api_moved()


@app.get("/api/admin/context")
def deprecated_admin_context() -> dict:
    _platform_api_moved()


@app.get("/api/rbac/red-flags")
def deprecated_rbac_red_flags() -> dict:
    _platform_api_moved()


@app.get("/api/rbac/transaction-monitoring")
def deprecated_rbac_transaction_monitoring() -> dict:
    _platform_api_moved()


@app.get("/api/admin/workflow-templates")
def deprecated_workflow_templates() -> dict:
    _platform_api_moved()


@app.get("/api/workflows/{module_code}/{entity_type}")
def deprecated_get_workflow(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()


@app.post("/api/workflows/{module_code}/{entity_type}/draft")
def deprecated_create_workflow_draft(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()


@app.post("/api/workflows/{module_code}/{entity_type}/draft/validate")
def deprecated_validate_workflow_draft(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()


@app.post("/api/workflows/{module_code}/{entity_type}/draft/publish")
def deprecated_publish_workflow_draft(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()


@app.post("/api/workflows/{module_code}/{entity_type}/draft/rollback")
def deprecated_rollback_workflow(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()


@app.patch("/api/workflows/{module_code}/{entity_type}/draft")
def deprecated_update_workflow_draft(module_code: str, entity_type: str) -> dict:
    _platform_api_moved()
