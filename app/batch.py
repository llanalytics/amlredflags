import logging
import threading
import uuid
from datetime import datetime, timezone

from app.analyzer import extract_red_flags
from app.config import MAX_PAGES_PER_SOURCE, SOURCES
from app.database import SessionLocal
from app.fetcher import fetch_paginated_documents
from app.models import BatchRun, RedFlag, SourceDocument

logger = logging.getLogger(__name__)

_batch_lock = threading.Lock()
_active_batch_id: str | None = None


def queue_batch_run() -> tuple[bool, str, str | None]:
    global _active_batch_id
    with _batch_lock:
        if _active_batch_id is not None:
            return False, "Batch already running", _active_batch_id

    batch_id = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        run = BatchRun(
            batch_id=batch_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        with _batch_lock:
            _active_batch_id = batch_id
        threading.Thread(target=_run_batch, args=(batch_id,), daemon=True).start()
        return True, "Batch started", batch_id
    finally:
        db.close()


def _run_batch(batch_id: str) -> None:
    global _active_batch_id
    db = SessionLocal()
    try:
        run = db.query(BatchRun).filter(BatchRun.batch_id == batch_id).first()
        if run is None:
            logger.error("Batch run missing for id=%s", batch_id)
            return

        items_fetched = 0
        flags_extracted = 0
        errors = 0

        for source in SOURCES:
            source_name = source["name"]
            source_url = source["url"]
            max_pages = int(source.get("max_pages", MAX_PAGES_PER_SOURCE))
            try:
                documents = fetch_paginated_documents(source_url, max_pages=max_pages)
                for document_url, title, text in documents:
                    existing = db.query(SourceDocument).filter(SourceDocument.url == document_url).first()

                    if existing is None:
                        doc = SourceDocument(
                            batch_id=batch_id,
                            source_name=source_name,
                            title=title,
                            url=document_url,
                            raw_text=text,
                            processed=False,
                        )
                        db.add(doc)
                        db.flush()
                    else:
                        doc = existing
                        doc.batch_id = batch_id
                        doc.source_name = source_name
                        doc.title = title
                        doc.raw_text = text
                        doc.processed = False
                        db.query(RedFlag).filter(RedFlag.document_id == doc.id).delete()

                    matches = extract_red_flags(text)
                    for match in matches:
                        db.add(
                            RedFlag(
                                document_id=doc.id,
                                category=match["category"],
                                severity=match["severity"],
                                text=match["text"],
                                confidence_score=match["confidence_score"],
                            )
                        )

                    doc.processed = True
                    db.commit()

                    items_fetched += 1
                    flags_extracted += len(matches)
            except Exception:
                errors += 1
                logger.exception("Source processing failed for %s (%s)", source_name, source_url)
                db.rollback()

        run.items_fetched = items_fetched
        run.flags_extracted = flags_extracted
        run.errors = errors
        run.status = "completed_with_errors" if errors else "completed"
        run.ended_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        logger.exception("Fatal batch failure for batch_id=%s", batch_id)
        db.rollback()
        run = db.query(BatchRun).filter(BatchRun.batch_id == batch_id).first()
        if run is not None:
            run.status = "failed"
            run.ended_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
        with _batch_lock:
            if _active_batch_id == batch_id:
                _active_batch_id = None
