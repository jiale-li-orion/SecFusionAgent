from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.enrichment.graph.fix_boundary import DeterministicFixBoundaryService
from packages.enrichment.graph.github_references import GitHubReferenceGraphService
from packages.enrichment.planner import VulnerabilityEnrichmentPlanner
from packages.enrichment.runtime.executor import DefaultEnrichmentOperatorExecutor
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.service import VulnerabilityEnrichmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.storage.artifacts import ArtifactStore
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.config import Settings
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.registry.loader import load_source_definitions

DEFAULT_VULNERABILITY_PROVIDER_IDS = (
    "cisa-kev",
    "github-global-advisories",
    "osv-vulnerabilities",
    "github-target-repos",
)


def create_configured_enrichment_runtime(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    artifact_store: ArtifactStore,
) -> EnrichmentRoleRuntime:
    source_definitions = {
        item.source_id: item
        for item in load_source_definitions(Path(settings.source_registry_path))
    }
    adapters = {
        source_id: create_source_adapter(source_definitions[source_id], client, settings)
        for source_id in DEFAULT_VULNERABILITY_PROVIDER_IDS
    }
    acquisition = AcquisitionService(session_factory)
    evidence_ingress = EvidenceIngress(artifact_store)
    writer = EvidenceBackedKnowledgeWriter()
    provider_service = VulnerabilityEnrichmentService(
        session_factory,
        acquisition,
        evidence_ingress,
        writer,
        VulnerabilityEnrichmentPlanner(),
        source_definitions,
        adapters,
    )
    graph_service = GitHubReferenceGraphService(
        session_factory,
        acquisition,
        evidence_ingress,
        writer,
        source_definitions,
        adapters,
    )
    fix_service = DeterministicFixBoundaryService(
        session_factory,
        acquisition,
        evidence_ingress,
        writer,
        source_definitions,
        adapters,
    )
    return EnrichmentRoleRuntime(
        session_factory,
        DefaultEnrichmentOperatorExecutor(
            provider_service,
            graph_service,
            fix_service,
        ),
        stream_name=settings.task_event_stream_name,
    )
