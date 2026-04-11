"""create platform and workflow tables

Revision ID: 20260407_0003
Revises: 20260404_0002
Create Date: 2026-04-07 07:10:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260407_0003"
down_revision = "20260404_0002"
branch_labels = None
depends_on = None


def _target_schema(bind) -> str | None:
    if bind.dialect.name == "sqlite":
        return None
    return os.getenv("DB_SCHEMA", "amlredflags_v2")


def _fk(schema: str | None, table: str, column: str) -> str:
    if schema:
        return f"{schema}.{table}.{column}"
    return f"{table}.{column}"


def upgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("name", name=op.f("uq_tenants_name")),
        schema=schema,
    )

    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_users")),
        sa.UniqueConstraint("email", name=op.f("uq_app_users_email")),
        schema=schema,
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
        schema=schema,
    )

    op.create_table(
        "tenant_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("app_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_tenant_users_tenant_id_tenants")),
        sa.ForeignKeyConstraint(["app_user_id"], [_fk(schema, "app_users", "id")], name=op.f("fk_tenant_users_app_user_id_app_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_users")),
        sa.UniqueConstraint("tenant_id", "app_user_id", name=op.f("uq_tenant_users_tenant_id_app_user_id")),
        schema=schema,
    )

    op.create_table(
        "tenant_user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_user_id"], [_fk(schema, "tenant_users", "id")], name=op.f("fk_tenant_user_roles_tenant_user_id_tenant_users")),
        sa.ForeignKeyConstraint(["role_id"], [_fk(schema, "roles", "id")], name=op.f("fk_tenant_user_roles_role_id_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_user_roles")),
        sa.UniqueConstraint("tenant_user_id", "role_id", name=op.f("uq_tenant_user_roles_tenant_user_id_role_id")),
        schema=schema,
    )

    op.create_table(
        "platform_user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["app_user_id"], [_fk(schema, "app_users", "id")], name=op.f("fk_platform_user_roles_app_user_id_app_users")),
        sa.ForeignKeyConstraint(["role_id"], [_fk(schema, "roles", "id")], name=op.f("fk_platform_user_roles_role_id_roles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_user_roles")),
        sa.UniqueConstraint("app_user_id", "role_id", name=op.f("uq_platform_user_roles_app_user_id_role_id")),
        schema=schema,
    )

    op.create_table(
        "tenant_module_entitlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("enabled_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_tenant_module_entitlements_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_module_entitlements")),
        sa.UniqueConstraint("tenant_id", "module_code", name=op.f("uq_tenant_module_entitlements_tenant_id_module_code")),
        schema=schema,
    )

    op.create_table(
        "business_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_business_units_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_units")),
        sa.UniqueConstraint("tenant_id", "code", name=op.f("uq_business_units_tenant_id_code")),
        schema=schema,
    )

    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_system_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definitions")),
        schema=schema,
    )

    op.create_table(
        "workflow_definition_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_definition_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workflow_definition_id"], [_fk(schema, "workflow_definitions", "id")], name=op.f("fk_workflow_definition_versions_workflow_definition_id_workflow_definitions")),
        sa.ForeignKeyConstraint(["published_by_user_id"], [_fk(schema, "app_users", "id")], name=op.f("fk_workflow_definition_versions_published_by_user_id_app_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definition_versions")),
        sa.UniqueConstraint("workflow_definition_id", "version_no", name=op.f("uq_workflow_definition_versions_workflow_definition_id_version_no")),
        schema=schema,
    )

    op.create_table(
        "workflow_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_version_id", sa.Integer(), nullable=False),
        sa.Column("state_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["workflow_version_id"], [_fk(schema, "workflow_definition_versions", "id")], name=op.f("fk_workflow_states_workflow_version_id_workflow_definition_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_states")),
        sa.UniqueConstraint("workflow_version_id", "state_code", name=op.f("uq_workflow_states_workflow_version_id_state_code")),
        schema=schema,
    )

    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_version_id", sa.Integer(), nullable=False),
        sa.Column("transition_code", sa.String(length=64), nullable=False),
        sa.Column("from_state_code", sa.String(length=64), nullable=False),
        sa.Column("to_state_code", sa.String(length=64), nullable=False),
        sa.Column("requires_comment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workflow_version_id"], [_fk(schema, "workflow_definition_versions", "id")], name=op.f("fk_workflow_transitions_workflow_version_id_workflow_definition_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transitions")),
        sa.UniqueConstraint("workflow_version_id", "transition_code", name=op.f("uq_workflow_transitions_workflow_version_id_transition_code")),
        schema=schema,
    )

    op.create_table(
        "workflow_transition_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_transition_id", sa.Integer(), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["workflow_transition_id"], [_fk(schema, "workflow_transitions", "id")], name=op.f("fk_workflow_transition_roles_workflow_transition_id_workflow_transitions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transition_roles")),
        sa.UniqueConstraint("workflow_transition_id", "role_code", name=op.f("uq_workflow_transition_roles_workflow_transition_id_role_code")),
        schema=schema,
    )

    op.create_table(
        "tenant_workflow_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("workflow_version_id", sa.Integer(), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_tenant_workflow_bindings_tenant_id_tenants")),
        sa.ForeignKeyConstraint(["workflow_version_id"], [_fk(schema, "workflow_definition_versions", "id")], name=op.f("fk_tenant_workflow_bindings_workflow_version_id_workflow_definition_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_workflow_bindings")),
        sa.UniqueConstraint("tenant_id", "module_code", "entity_type", "active_from", name=op.f("uq_tenant_workflow_bindings_tenant_id_module_code_entity_type_active_from")),
        schema=schema,
    )

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_workflow_events_tenant_id_tenants")),
        sa.ForeignKeyConstraint(["actor_user_id"], [_fk(schema, "app_users", "id")], name=op.f("fk_workflow_events_actor_user_id_app_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_events")),
        schema=schema,
    )

    op.create_table(
        "api_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("module_code", sa.String(length=64), nullable=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], [_fk(schema, "tenants", "id")], name=op.f("fk_api_usage_events_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_usage_events")),
        schema=schema,
    )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)

    op.drop_table("api_usage_events", schema=schema)
    op.drop_table("workflow_events", schema=schema)
    op.drop_table("tenant_workflow_bindings", schema=schema)
    op.drop_table("workflow_transition_roles", schema=schema)
    op.drop_table("workflow_transitions", schema=schema)
    op.drop_table("workflow_states", schema=schema)
    op.drop_table("workflow_definition_versions", schema=schema)
    op.drop_table("workflow_definitions", schema=schema)
    op.drop_table("business_units", schema=schema)
    op.drop_table("tenant_module_entitlements", schema=schema)
    op.drop_table("platform_user_roles", schema=schema)
    op.drop_table("tenant_user_roles", schema=schema)
    op.drop_table("tenant_users", schema=schema)
    op.drop_table("roles", schema=schema)
    op.drop_table("app_users", schema=schema)
    op.drop_table("tenants", schema=schema)
