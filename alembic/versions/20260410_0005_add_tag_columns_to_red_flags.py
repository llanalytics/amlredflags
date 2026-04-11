"""add product/service tag columns to red_flags

Revision ID: 20260410_0005
Revises: 20260407_0004
Create Date: 2026-04-10 18:10:00
"""

from alembic import op
import sqlalchemy as sa
import os


revision = "20260410_0005"
down_revision = "20260407_0004"
branch_labels = None
depends_on = None


def _target_schema(bind) -> str | None:
    if bind.dialect.name == "sqlite":
        return None
    return os.getenv("DB_SCHEMA", "amlredflags_v2")


def upgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("red_flags", schema=schema)}

    if "product_tags_json" not in existing_columns:
        op.add_column("red_flags", sa.Column("product_tags_json", sa.Text(), nullable=True), schema=schema)
    if "service_tags_json" not in existing_columns:
        op.add_column("red_flags", sa.Column("service_tags_json", sa.Text(), nullable=True), schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    schema = _target_schema(bind)
    insp = sa.inspect(bind)
    existing_columns = {c["name"] for c in insp.get_columns("red_flags", schema=schema)}

    if "service_tags_json" in existing_columns:
        op.drop_column("red_flags", "service_tags_json", schema=schema)
    if "product_tags_json" in existing_columns:
        op.drop_column("red_flags", "product_tags_json", schema=schema)
