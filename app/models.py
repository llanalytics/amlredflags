from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    flags_extracted: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    red_flags: Mapped[list["RedFlag"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class RedFlag(Base):
    __tablename__ = "red_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    text: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[SourceDocument] = relationship(back_populates="red_flags")


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)  # platform | tenant
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantUser(Base):
    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "app_user_id", name="uq_tenant_users_tenant_id_app_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantUserRole(Base):
    __tablename__ = "tenant_user_roles"
    __table_args__ = (
        UniqueConstraint("tenant_user_id", "role_id", name="uq_tenant_user_roles_tenant_user_id_role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_user_id: Mapped[int] = mapped_column(ForeignKey("tenant_users.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformUserRole(Base):
    __tablename__ = "platform_user_roles"
    __table_args__ = (
        UniqueConstraint("app_user_id", "role_id", name="uq_platform_user_roles_app_user_id_role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantModuleEntitlement(Base):
    __tablename__ = "tenant_module_entitlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_code", name="uq_tenant_module_entitlements_tenant_id_module_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    module_code: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    enabled_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessUnit(Base):
    __tablename__ = "business_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_business_units_tenant_id_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    module_code: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowDefinitionVersion(Base):
    __tablename__ = "workflow_definition_versions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_definition_id",
            "version_no",
            name="uq_workflow_definition_versions_workflow_definition_id_version_no",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_definition_id: Mapped[int] = mapped_column(ForeignKey("workflow_definitions.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)  # draft | published | retired
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowState(Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        UniqueConstraint("workflow_version_id", "state_code", name="uq_workflow_states_workflow_version_id_state_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_version_id: Mapped[int] = mapped_column(ForeignKey("workflow_definition_versions.id"), index=True)
    state_code: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_version_id",
            "transition_code",
            name="uq_workflow_transitions_workflow_version_id_transition_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_version_id: Mapped[int] = mapped_column(ForeignKey("workflow_definition_versions.id"), index=True)
    transition_code: Mapped[str] = mapped_column(String(64))
    from_state_code: Mapped[str] = mapped_column(String(64), index=True)
    to_state_code: Mapped[str] = mapped_column(String(64), index=True)
    requires_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowTransitionRole(Base):
    __tablename__ = "workflow_transition_roles"
    __table_args__ = (
        UniqueConstraint(
            "workflow_transition_id",
            "role_code",
            name="uq_workflow_transition_roles_workflow_transition_id_role_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_transition_id: Mapped[int] = mapped_column(ForeignKey("workflow_transitions.id"), index=True)
    role_code: Mapped[str] = mapped_column(String(64), index=True)


class TenantWorkflowBinding(Base):
    __tablename__ = "tenant_workflow_bindings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "module_code",
            "entity_type",
            "active_from",
            name="uq_tenant_workflow_bindings_tenant_id_module_code_entity_type_active_from",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    module_code: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    workflow_version_id: Mapped[int] = mapped_column(ForeignKey("workflow_definition_versions.id"), index=True)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    module_code: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    from_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    event_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class APIUsageEvent(Base):
    __tablename__ = "api_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    module_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), index=True)
    method: Mapped[str] = mapped_column(String(16), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
