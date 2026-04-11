"""add tenant_id to workflow_definitions

Revision ID: 20260407_0004
Revises: 20260407_0003
Create Date: 2026-04-07 08:05:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260407_0004"
down_revision = "20260407_0003"
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
    is_sqlite = bind.dialect.name == "sqlite"
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("workflow_definitions", schema=schema)}
    existing_indexes = {ix["name"] for ix in insp.get_indexes("workflow_definitions", schema=schema)}
    existing_fk_names = {fk.get("name") for fk in insp.get_foreign_keys("workflow_definitions", schema=schema)}

    if "tenant_id" not in existing_columns:
        op.add_column(
            "workflow_definitions",
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            schema=schema,
        )

    ix_name = op.f("ix_workflow_definitions_tenant_id")
    if ix_name not in existing_indexes:
        op.create_index(ix_name, "workflow_definitions", ["tenant_id"], unique=False, schema=schema)

    fk_name = op.f("fk_workflow_definitions_tenant_id_tenants")
    if not is_sqlite and "tenant_id" in {c["name"] for c in insp.get_columns("workflow_definitions", schema=schema)} and fk_name not in existing_fk_names:
        op.create_foreign_key(
            fk_name,
            "workflow_definitions",
            "tenants",
            ["tenant_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    is_sqlite = bind.dialect.name == "sqlite"
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("workflow_definitions", schema=schema)}
    existing_indexes = {ix["name"] for ix in insp.get_indexes("workflow_definitions", schema=schema)}
    existing_fk_names = {fk.get("name") for fk in insp.get_foreign_keys("workflow_definitions", schema=schema)}

    if "tenant_id" in existing_columns:
        if not is_sqlite:
            fk_name = op.f("fk_workflow_definitions_tenant_id_tenants")
            if fk_name in existing_fk_names:
                op.drop_constraint(fk_name, "workflow_definitions", schema=schema, type_="foreignkey")
        if op.f("ix_workflow_definitions_tenant_id") in existing_indexes:
            op.drop_index(op.f("ix_workflow_definitions_tenant_id"), table_name="workflow_definitions", schema=schema)
        op.drop_column("workflow_definitions", "tenant_id", schema=schema)
