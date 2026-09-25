"""managed document corpus

Revision ID: 20260925_0006
Revises: 20260925_0005
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0006"
down_revision: str | None = "20260925_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("external_object_id", sa.String(length=256), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_id",
            "external_object_id",
            name="uq_document_source_external",
        ),
    )
    op.create_index("ix_documents_object_id", "documents", ["object_id"])
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_external_object_id", "documents", ["external_object_id"])

    op.create_table(
        "document_revisions",
        sa.Column("document_revision_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_revision", sa.String(length=256)),
        sa.Column("title", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("observation_id", name="uq_document_revision_observation"),
    )
    op.create_index(
        "ix_document_revisions_document_id",
        "document_revisions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_revisions_observation_id",
        "document_revisions",
        ["observation_id"],
    )
    op.create_index(
        "ix_document_revisions_external_revision",
        "document_revisions",
        ["external_revision"],
    )
    op.create_index(
        "ix_document_revisions_content_hash",
        "document_revisions",
        ["content_hash"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_revision_id",
            sa.String(length=36),
            sa.ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=256)),
        sa.Column("page_number", sa.Integer()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunker_version", sa.String(length=32), nullable=False),
        sa.Column("index_status", sa.String(length=32), nullable=False),
        sa.Column("embedding_model", sa.String(length=128)),
        sa.Column("embedding_version", sa.String(length=128)),
        sa.UniqueConstraint(
            "document_revision_id",
            "ordinal",
            name="uq_document_chunk_revision_ordinal",
        ),
    )
    op.create_index(
        "ix_document_chunks_document_revision_id",
        "document_chunks",
        ["document_revision_id"],
    )
    op.create_index("ix_document_chunks_page_number", "document_chunks", ["page_number"])
    op.create_index("ix_document_chunks_content_hash", "document_chunks", ["content_hash"])

    op.create_table(
        "insight_candidates",
        sa.Column("insight_candidate_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_revision_id",
            sa.String(length=36),
            sa.ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_maturity", sa.String(length=64), nullable=False),
        sa.Column("promotion_state", sa.String(length=32), nullable=False),
        sa.Column("related_object_ids", sa.JSON(), nullable=False),
        sa.Column("related_claim_ids", sa.JSON(), nullable=False),
        sa.Column("related_relation_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_insight_candidates_document_revision_id",
        "insight_candidates",
        ["document_revision_id"],
    )
    op.create_index(
        "ix_insight_candidates_change_type",
        "insight_candidates",
        ["change_type"],
    )
    op.create_index(
        "ix_insight_candidates_evidence_maturity",
        "insight_candidates",
        ["evidence_maturity"],
    )
    op.create_index(
        "ix_insight_candidates_promotion_state",
        "insight_candidates",
        ["promotion_state"],
    )


def downgrade() -> None:
    op.drop_table("insight_candidates")
    op.drop_table("document_chunks")
    op.drop_table("document_revisions")
    op.drop_table("documents")
