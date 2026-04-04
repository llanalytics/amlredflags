from datetime import datetime
from pydantic import BaseModel


class HealthResponse(BaseModel):
    success: bool
    status: str
    red_flags_count: int
    unique_sources_count: int
    total_batches_processed: int
    last_batch_id: str | None
    last_batch_status: str | None
    last_batch_failure_reason: str | None


class TriggerBatchResponse(BaseModel):
    success: bool
    message: str
    batch_id: str


class BatchStatusResponse(BaseModel):
    success: bool
    running: bool
    last_batch_id: str | None
    last_status: str | None
    started_at: datetime | None
    ended_at: datetime | None
    last_failure_reason: str | None
    last_batch_red_flags_added: int
    last_batch_unique_sources_added: int


class ResetResponse(BaseModel):
    success: bool
    message: str
    deleted_red_flags: int
    deleted_source_documents: int
    deleted_batch_runs: int
