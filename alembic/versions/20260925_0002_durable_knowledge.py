"""durable evidence and canonical knowledge

Revision ID: 20260925_0002
Revises: 20260925_0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0002"
down_revision: str | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("observation_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=128),
            sa.ForeignKey("sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "acquisition_run_id",
            sa.String(length=36),
            sa.ForeignKey("acquisition_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("external_object_id", sa.String(length=256), nullable=False),
        sa.Column("external_revision", sa.String(length=256)),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_observations_idempotency_key"),
    )
    op.create_index("ix_observations_source_id", "observations", ["source_id"])
    op.create_index("ix_observations_acquisition_run_id", "observations", ["acquisition_run_id"])
    op.create_index("ix_observations_external_object_id", "observations", ["external_object_id"])
    op.create_index("ix_observations_external_revision", "observations", ["external_revision"])
    op.create_index("ix_observations_content_hash", "observations", ["content_hash"])

    op.create_table(
        "evidence_artifacts",
        sa.Column("artifact_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("access_rights", sa.JSON(), nullable=False),
        sa.Column("trust_class", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "observation_id",
            "content_hash",
            name="uq_evidence_artifact_observation_hash",
        ),
    )
    op.create_index(
        "ix_evidence_artifacts_observation_id",
        "evidence_artifacts",
        ["observation_id"],
    )
    op.create_index("ix_evidence_artifacts_content_hash", "evidence_artifacts", ["content_hash"])

    op.create_table(
        "knowledge_revisions",
        sa.Column("revision", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cause_processing_run_id", sa.String(length=36)),
        sa.Column(
            "cause_observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="SET NULL"),
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_knowledge_revisions_cause_processing_run_id",
        "knowledge_revisions",
        ["cause_processing_run_id"],
    )
    op.create_index(
        "ix_knowledge_revisions_cause_observation_id",
        "knowledge_revisions",
        ["cause_observation_id"],
    )

    op.create_table(
        "objects",
        sa.Column("object_id", sa.String(length=36), primary_key=True),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_key", sa.String(length=512), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "superseded_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint("object_type", "canonical_key", name="uq_objects_type_canonical_key"),
    )
    op.create_index("ix_objects_object_type", "objects", ["object_type"])

    op.create_table(
        "external_identifiers",
        sa.Column("external_identifier_id", sa.String(length=36), primary_key=True),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column(
            "object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("namespace", "value", name="uq_external_identifiers_namespace_value"),
    )
    op.create_index("ix_external_identifiers_namespace", "external_identifiers", ["namespace"])
    op.create_index("ix_external_identifiers_value", "external_identifiers", ["value"])
    op.create_index("ix_external_identifiers_object_id", "external_identifiers", ["object_id"])

    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "subject_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("qualifier", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column(
            "processing_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "superseded_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
        ),
    )
    for name, column in [
        ("ix_claims_subject_id", "subject_id"),
        ("ix_claims_predicate", "predicate"),
        ("ix_claims_origin", "origin"),
        ("ix_claims_lifecycle", "lifecycle"),
        ("ix_claims_processing_run_id", "processing_run_id"),
    ]:
        op.create_index(name, "claims", [column])

    op.create_table(
        "relations",
        sa.Column("relation_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=128), nullable=False),
        sa.Column(
            "target_object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qualifier", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column(
            "processing_run_id",
            sa.String(length=36),
            sa.ForeignKey("processing_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "superseded_revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="RESTRICT"),
        ),
    )
    for name, column in [
        ("ix_relations_source_object_id", "source_object_id"),
        ("ix_relations_relation_type", "relation_type"),
        ("ix_relations_target_object_id", "target_object_id"),
        ("ix_relations_origin", "origin"),
        ("ix_relations_lifecycle", "lifecycle"),
        ("ix_relations_processing_run_id", "processing_run_id"),
    ]:
        op.create_index(name, "relations", [column])

    op.create_table(
        "evidence_links",
        sa.Column("evidence_link_id", sa.String(length=36), primary_key=True),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column(
            "observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=36),
            sa.ForeignKey("evidence_artifacts.artifact_id", ondelete="SET NULL"),
        ),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("locator_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "target_kind",
            "target_id",
            "observation_id",
            "locator_hash",
            name="uq_evidence_link_target",
        ),
    )
    op.create_index("ix_evidence_links_target_kind", "evidence_links", ["target_kind"])
    op.create_index("ix_evidence_links_target_id", "evidence_links", ["target_id"])
    op.create_index("ix_evidence_links_observation_id", "evidence_links", ["observation_id"])
    op.create_index("ix_evidence_links_artifact_id", "evidence_links", ["artifact_id"])

    op.create_table(
        "knowledge_changes",
        sa.Column("change_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "revision",
            sa.Integer(),
            sa.ForeignKey("knowledge_revisions.revision", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("changed_ids", sa.JSON(), nullable=False),
        sa.Column("cause_processing_run_id", sa.String(length=36)),
        sa.Column(
            "cause_observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="SET NULL"),
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_changes_revision", "knowledge_changes", ["revision"])
    op.create_index(
        "ix_knowledge_changes_cause_processing_run_id",
        "knowledge_changes",
        ["cause_processing_run_id"],
    )
    op.create_index(
        "ix_knowledge_changes_cause_observation_id",
        "knowledge_changes",
        ["cause_observation_id"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_changes")
    op.drop_table("evidence_links")
    op.drop_table("relations")
    op.drop_table("claims")
    op.drop_table("external_identifiers")
    op.drop_table("objects")
    op.drop_table("knowledge_revisions")
    op.drop_table("evidence_artifacts")
    op.drop_table("observations")
