"""add product question sessions

Revision ID: 20260930_0027
Revises: 20260929_0026
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_0027"
down_revision: str | None = "20260929_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_sessions",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("principal", sa.String(length=256), nullable=False),
        sa.Column("state_carry_policy", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_sessions_principal", "question_sessions", ["principal"])
    op.create_index("ix_question_sessions_updated_at", "question_sessions", ["updated_at"])

    op.create_table(
        "question_session_turns",
        sa.Column("turn_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("question_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("task_kind", sa.String(length=64), nullable=False),
        sa.Column("target_object_ids", sa.JSON(), nullable=False),
        sa.Column("knowledge_revision", sa.Integer(), nullable=True),
        sa.Column("context_id", sa.String(length=128), nullable=True),
        sa.Column("decision_ref", sa.String(length=128), nullable=True),
        sa.Column("investigation_ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "turn_index", name="uq_question_session_turn_index"
        ),
        sa.UniqueConstraint(
            "session_id", "request_id", name="uq_question_session_request"
        ),
    )
    op.create_index(
        "ix_question_session_turns_session_id", "question_session_turns", ["session_id"]
    )
    op.create_index(
        "ix_question_session_turns_request_id", "question_session_turns", ["request_id"]
    )
    op.create_index(
        "ix_question_session_turns_knowledge_revision",
        "question_session_turns",
        ["knowledge_revision"],
    )
    op.create_index(
        "ix_question_session_turns_context_id", "question_session_turns", ["context_id"]
    )
    op.create_index(
        "ix_question_session_turns_decision_ref", "question_session_turns", ["decision_ref"]
    )
    op.create_index(
        "ix_question_session_turns_investigation_ref",
        "question_session_turns",
        ["investigation_ref"],
    )


def downgrade() -> None:
    op.drop_table("question_session_turns")
    op.drop_table("question_sessions")
