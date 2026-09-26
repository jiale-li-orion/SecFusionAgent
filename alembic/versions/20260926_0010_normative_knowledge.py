"""normative knowledge projection

Revision ID: 20260926_0010
Revises: 20260926_0009
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260926_0010"
down_revision: str | None = "20260926_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normative_documents",
        sa.Column("normative_document_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_normative_document_managed_document"),
    )
    op.create_index("ix_normative_documents_document_id", "normative_documents", ["document_id"])
    op.create_index("ix_normative_documents_source_id", "normative_documents", ["source_id"])

    op.create_table(
        "normative_document_revisions",
        sa.Column("normative_revision_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "normative_document_id",
            sa.String(length=36),
            sa.ForeignKey("normative_documents.normative_document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_revision_id",
            sa.String(length=36),
            sa.ForeignKey("document_revisions.document_revision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("issuer", sa.Text()),
        sa.Column("jurisdiction", sa.String(length=256)),
        sa.Column("document_type", sa.String(length=128)),
        sa.Column("binding_status", sa.String(length=128)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("status", sa.String(length=64)),
        sa.Column("external_version", sa.String(length=256)),
        sa.Column("official_url", sa.Text()),
        sa.Column("access_rights", sa.JSON(), nullable=False),
        sa.Column("full_text_available", sa.Boolean(), nullable=False),
        sa.Column("supersedes_refs", sa.JSON(), nullable=False),
        sa.Column("amends_refs", sa.JSON(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("metadata_facts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_revision_id",
            name="uq_normative_revision_document_revision",
        ),
    )
    for column in (
        "normative_document_id",
        "document_revision_id",
        "processing_run_id",
        "jurisdiction",
        "document_type",
        "binding_status",
        "status",
    ):
        op.create_index(
            f"ix_normative_document_revisions_{column}",
            "normative_document_revisions",
            [column],
        )

    op.create_table(
        "normative_requirements",
        sa.Column("requirement_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "normative_revision_id",
            sa.String(length=36),
            sa.ForeignKey("normative_document_revisions.normative_revision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_clause", sa.Text()),
        sa.Column("modality", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("object_text", sa.Text(), nullable=False),
        sa.Column("condition_text", sa.Text()),
        sa.Column("exception_text", sa.Text()),
        sa.Column("jurisdiction", sa.String(length=256)),
        sa.Column("applicability", sa.JSON(), nullable=False),
        sa.Column("applicability_status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("risk_mapping", sa.JSON(), nullable=False),
        sa.Column("evidence_locator", sa.JSON(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column(
            "superseded_by_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "normative_revision_id",
        "processing_run_id",
        "modality",
        "jurisdiction",
        "applicability_status",
        "lifecycle",
        "superseded_by_run_id",
    ):
        op.create_index(
            f"ix_normative_requirements_{column}",
            "normative_requirements",
            [column],
        )

    op.create_table(
        "normative_controls",
        sa.Column("control_id", sa.String(length=36), primary_key=True),
        sa.Column("canonical_key", sa.String(length=256), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canonical_key", name="uq_normative_control_canonical_key"),
    )
    op.create_index("ix_normative_controls_canonical_key", "normative_controls", ["canonical_key"])

    op.create_table(
        "normative_control_evidence",
        sa.Column("control_evidence_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "control_id",
            sa.String(length=36),
            sa.ForeignKey("normative_controls.control_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "normative_revision_id",
            sa.String(length=36),
            sa.ForeignKey("normative_document_revisions.normative_revision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_locator", sa.JSON(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_normative_control_evidence_control_id",
        "normative_control_evidence",
        ["control_id"],
    )
    op.create_index(
        "ix_normative_control_evidence_normative_revision_id",
        "normative_control_evidence",
        ["normative_revision_id"],
    )
    op.create_index(
        "ix_normative_control_evidence_processing_run_id",
        "normative_control_evidence",
        ["processing_run_id"],
    )

    op.create_table(
        "requirement_control_mappings",
        sa.Column("mapping_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("normative_requirements.requirement_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "control_id",
            sa.String(length=36),
            sa.ForeignKey("normative_controls.control_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_locator", sa.JSON(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "requirement_id",
            "control_id",
            "relation_type",
            name="uq_requirement_control_relation",
        ),
    )
    op.create_index(
        "ix_requirement_control_mappings_requirement_id",
        "requirement_control_mappings",
        ["requirement_id"],
    )
    op.create_index(
        "ix_requirement_control_mappings_control_id",
        "requirement_control_mappings",
        ["control_id"],
    )
    op.create_index(
        "ix_requirement_control_mappings_relation_type",
        "requirement_control_mappings",
        ["relation_type"],
    )


def downgrade() -> None:
    op.drop_table("requirement_control_mappings")
    op.drop_table("normative_control_evidence")
    op.drop_table("normative_controls")
    op.drop_table("normative_requirements")
    op.drop_table("normative_document_revisions")
    op.drop_table("normative_documents")
