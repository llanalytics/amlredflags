"""add failure_reason to batch_runs

Revision ID: 20260404_0002
Revises: 20260402_0001
Create Date: 2026-04-04 07:20:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260404_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def _target_schema(bind) -> str | None:
    if bind.dialect.name == "sqlite":
        return None
    raw = os.getenv("DB_SCHEMA", "amlredflags_v2").strip().strip("'\"")
    if raw.lower() in {"", "none", "null"}:
        return None
    return raw


def upgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    op.add_column("batch_runs", sa.Column("failure_reason", sa.Text(), nullable=True), schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    op.drop_column("batch_runs", "failure_reason", schema=schema)
