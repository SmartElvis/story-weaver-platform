"""add arc_plan to projects

Revision ID: 0002_add_arc_plan
Revises: 0001_baseline
Create Date: 2026-07-28 00:00:00.000000

Adds the structured "故事藍圖" (arc plan) JSONB column to projects. The Architect
agent generates and maintains it; generation agents read a rendering of it so
each chapter advances the overall three-act arc instead of developing in
isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_add_arc_plan"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("arc_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "arc_plan")
