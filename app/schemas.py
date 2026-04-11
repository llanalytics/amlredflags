from datetime import datetime
from pydantic import BaseModel


class HealthResponse(BaseModel):
    success: bool
    status: str
    red_flags_count: int
    unique_sources_count: int
    total_documents_count: int
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


class RedFlagCatalogItem(BaseModel):
    id: int
    source_name: str
    source_url: str
    source_title: str
    category: str
    severity: str
    text: str
    confidence_score: int | None
    product_tags: list[str] = []
    service_tags: list[str] = []
    created_at: datetime | None


class RedFlagCatalogResponse(BaseModel):
    success: bool
    total: int
    limit: int
    offset: int
    data: list[RedFlagCatalogItem]


class WorkflowCloneFrom(BaseModel):
    source: str | None = None
    workflow_definition_id: int | None = None
    workflow_version_id: int | None = None


class WorkflowDraftCreateRequest(BaseModel):
    name: str | None = None
    clone_from: WorkflowCloneFrom | None = None


class WorkflowDraftCreateResponse(BaseModel):
    success: bool
    workflow_definition_id: int
    workflow_version_id: int
    status: str


class WorkflowValidateRequest(BaseModel):
    version_id: int


class WorkflowValidateIssue(BaseModel):
    code: str
    message: str


class WorkflowValidateResponse(BaseModel):
    valid: bool
    errors: list[WorkflowValidateIssue]
    warnings: list[str]


class WorkflowPublishRequest(BaseModel):
    version_id: int
    effective_at: str | None = None
    publish_comment: str | None = None


class WorkflowPublishResponse(BaseModel):
    success: bool
    workflow_definition_id: int
    workflow_version_id: int
    status: str
    binding: dict


class WorkflowRollbackRequest(BaseModel):
    target_workflow_version_id: int
    effective_at: str | None = None
    reason: str | None = None


class WorkflowRollbackResponse(BaseModel):
    success: bool
    active_workflow_version_id: int
    rolled_back_from_workflow_version_id: int | None


class WorkflowDraftStateInput(BaseModel):
    state_code: str
    display_name: str
    is_initial: bool = False
    is_terminal: bool = False


class WorkflowDraftTransitionInput(BaseModel):
    transition_code: str
    from_state_code: str
    to_state_code: str
    requires_comment: bool = False
    allowed_roles: list[str] = []


class WorkflowDraftUpdateRequest(BaseModel):
    version_id: int
    states: list[WorkflowDraftStateInput]
    transitions: list[WorkflowDraftTransitionInput]


class WorkflowDraftUpdateResponse(BaseModel):
    success: bool
    workflow_version_id: int
    status: str
    updated_at: str
