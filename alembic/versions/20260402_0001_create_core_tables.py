"""create core tables

Revision ID: 20260402_0001
Revises:
Create Date: 2026-04-02 08:40:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260402_0001"
down_revision = None
branch_labels = None
depends_on = None


def _target_schema(bind) -> str | None:
    if bind.dialect.name == "sqlite":
        return None
    return os.getenv("DB_SCHEMA", "amlredflags_v2")


def upgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    if schema:
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    op.create_table(
        "batch_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flags_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batch_runs")),
        sa.UniqueConstraint("batch_id", name=op.f("uq_batch_runs_batch_id")),
        schema=schema,
    )
    op.create_index(op.f("ix_batch_runs_id"), "batch_runs", ["id"], unique=False, schema=schema)
    op.create_index(op.f("ix_batch_runs_batch_id"), "batch_runs", ["batch_id"], unique=False, schema=schema)
    op.create_index(op.f("ix_batch_runs_status"), "batch_runs", ["status"], unique=False, schema=schema)

    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_documents")),
        sa.UniqueConstraint("url", name=op.f("uq_source_documents_url")),
        schema=schema,
    )
    op.create_index(op.f("ix_source_documents_id"), "source_documents", ["id"], unique=False, schema=schema)
    op.create_index(op.f("ix_source_documents_batch_id"), "source_documents", ["batch_id"], unique=False, schema=schema)
    op.create_index(op.f("ix_source_documents_source_name"), "source_documents", ["source_name"], unique=False, schema=schema)
    op.create_index(op.f("ix_source_documents_url"), "source_documents", ["url"], unique=False, schema=schema)
    op.create_index(op.f("ix_source_documents_processed"), "source_documents", ["processed"], unique=False, schema=schema)

    op.create_table(
        "red_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            [f"{schema}.source_documents.id" if schema else "source_documents.id"],
            name=op.f("fk_red_flags_document_id_source_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_red_flags")),
        schema=schema,
    )
    op.create_index(op.f("ix_red_flags_id"), "red_flags", ["id"], unique=False, schema=schema)
    op.create_index(op.f("ix_red_flags_document_id"), "red_flags", ["document_id"], unique=False, schema=schema)
    op.create_index(op.f("ix_red_flags_category"), "red_flags", ["category"], unique=False, schema=schema)
    op.create_index(op.f("ix_red_flags_severity"), "red_flags", ["severity"], unique=False, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)

    op.drop_index(op.f("ix_red_flags_severity"), table_name="red_flags", schema=schema)
    op.drop_index(op.f("ix_red_flags_category"), table_name="red_flags", schema=schema)
    op.drop_index(op.f("ix_red_flags_document_id"), table_name="red_flags", schema=schema)
    op.drop_index(op.f("ix_red_flags_id"), table_name="red_flags", schema=schema)
    op.drop_table("red_flags", schema=schema)

    op.drop_index(op.f("ix_source_documents_processed"), table_name="source_documents", schema=schema)
    op.drop_index(op.f("ix_source_documents_url"), table_name="source_documents", schema=schema)
    op.drop_index(op.f("ix_source_documents_source_name"), table_name="source_documents", schema=schema)
    op.drop_index(op.f("ix_source_documents_batch_id"), table_name="source_documents", schema=schema)
    op.drop_index(op.f("ix_source_documents_id"), table_name="source_documents", schema=schema)
    op.drop_table("source_documents", schema=schema)

    op.drop_index(op.f("ix_batch_runs_status"), table_name="batch_runs", schema=schema)
    op.drop_index(op.f("ix_batch_runs_batch_id"), table_name="batch_runs", schema=schema)
    op.drop_index(op.f("ix_batch_runs_id"), table_name="batch_runs", schema=schema)
    op.drop_table("batch_runs", schema=schema)
