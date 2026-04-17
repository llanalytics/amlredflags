"""add raw prediction columns to red_flags

Revision ID: 20260411_0006
Revises: 20260410_0005
Create Date: 2026-04-11 09:20:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260411_0006"
down_revision = "20260410_0005"
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
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("red_flags", schema=schema)}

    if "raw_category" not in existing_columns:
        op.add_column("red_flags", sa.Column("raw_category", sa.String(length=256), nullable=True), schema=schema)
    if "raw_product_tags_json" not in existing_columns:
        op.add_column("red_flags", sa.Column("raw_product_tags_json", sa.Text(), nullable=True), schema=schema)
    if "raw_service_tags_json" not in existing_columns:
        op.add_column("red_flags", sa.Column("raw_service_tags_json", sa.Text(), nullable=True), schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("red_flags", schema=schema)}

    if "raw_service_tags_json" in existing_columns:
        op.drop_column("red_flags", "raw_service_tags_json", schema=schema)
    if "raw_product_tags_json" in existing_columns:
        op.drop_column("red_flags", "raw_product_tags_json", schema=schema)
    if "raw_category" in existing_columns:
        op.drop_column("red_flags", "raw_category", schema=schema)
