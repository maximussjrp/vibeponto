"""baseline schema with hardening round 2 fields

Revision ID: 20260917_0001
Revises:
Create Date: 2026-09-17 00:00:00
"""
import app.models.models  # noqa: F401
from alembic import op
from app.core.database import Base

revision = "20260917_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
