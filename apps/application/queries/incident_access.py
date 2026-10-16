"""Read-time rights checks for public curated incident projections."""

from sqlalchemy import exists, or_, select

from packages.intelligence.storage.evidence_models import EvidenceArtifactModel
from packages.intelligence.storage.incident_models import (
    IncidentSourceLinkModel,
    SecurityIncidentModel,
)
from packages.sources.storage.models import SourceModel


def public_curated_incident_clause():
    link = IncidentSourceLinkModel
    artifact = EvidenceArtifactModel
    has_artifact = exists(
        select(artifact.artifact_id).where(artifact.observation_id == link.observation_id)
    )
    private_artifact = exists(
        select(artifact.artifact_id).where(
            artifact.observation_id == link.observation_id,
            or_(
                artifact.access_rights["classification"].as_string().is_(None),
                artifact.access_rights["classification"].as_string() != "public",
            ),
        )
    )
    invalid_link = exists(
        select(link.source_link_id)
        .outerjoin(SourceModel, SourceModel.source_id == link.source_id)
        .where(
            link.incident_id == SecurityIncidentModel.incident_id,
            or_(
                SourceModel.source_id.is_(None),
                SourceModel.access_rights["classification"].as_string().is_(None),
                SourceModel.access_rights["classification"].as_string() != "public",
                ~has_artifact,
                private_artifact,
            ),
        )
    )
    has_link = exists(
        select(link.source_link_id).where(link.incident_id == SecurityIncidentModel.incident_id)
    )
    return has_link & ~invalid_link


def curated_visibility_clause():
    # Existing non-curated projections retain their established access contract.
    return or_(
        SecurityIncidentModel.watch_state["historical_backfill"].as_boolean().is_(None),
        SecurityIncidentModel.watch_state["historical_backfill"].as_boolean().is_(False),
        public_curated_incident_clause(),
    )
