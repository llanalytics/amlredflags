from datetime import datetime
from pydantic import BaseModel


class HealthResponse(BaseModel):
    success: bool
    status: str
    red_flags_count: int
    unique_sources_count: int
    total_batches_processed: int


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
    last_batch_red_flags_added: int
    last_batch_unique_sources_added: int
