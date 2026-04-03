from fastapi import FastAPI, HTTPException
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone

from app.batch import queue_batch_run
from app.database import SessionLocal
from app.models import BatchRun, RedFlag, SourceDocument
from app.schemas import BatchStatusResponse, HealthResponse, TriggerBatchResponse

app = FastAPI(title="AML Red Flags v2")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db = SessionLocal()
    try:
        count = db.query(RedFlag).count()
        unique_sources = db.query(SourceDocument.source_name).distinct().count()
        total_batches = db.query(BatchRun).count()
        return HealthResponse(
            success=True,
            status="healthy",
            red_flags_count=count,
            unique_sources_count=unique_sources,
            total_batches_processed=total_batches,
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
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
    finally:
        db.close()
