"""widen prompt assembly task contract identity

Revision ID: 20261002_0029
Revises: 20260930_0028
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_0029"
down_revision: str | None = "20260930_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "prompt_assembly_records",
        "task_contract_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "prompt_assembly_records",
        "task_contract_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
