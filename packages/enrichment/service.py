from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.enrichment.planner import VulnerabilityEnrichmentPlanner
from packages.enrichment.processors.cisa_kev import CISAKEVMapper
from packages.enrichment.processors.github_advisory import GitHubAdvisoryMapper
from packages.enrichment.processors.osv import OSVMapper
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.contracts import EnrichmentMapper
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.monitoring.acquisition.service import AcquisitionService
from packages.sources.contracts import SourceAdapter, SourceDefinition


class VulnerabilityEnrichmentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        acquisition: AcquisitionService,
        evidence_ingress: EvidenceIngress,
        writer: EvidenceBackedKnowledgeWriter,
        planner: VulnerabilityEnrichmentPlanner,
        sources: dict[str, SourceDefinition],
        adapters: dict[str, SourceAdapter],
    ) -> None:
        self._session_factory = session_factory
        self._acquisition = acquisition
        self._evidence_ingress = evidence_ingress
        self._writer = writer
        self._planner = planner
        self._sources = sources
        self._adapters = adapters
        self._mappers: dict[str, EnrichmentMapper] = {
            "cisa_kev": CISAKEVMapper(),
            "github_global_advisory": GitHubAdvisoryMapper(),
            "osv": OSVMapper(),
        }

    async def enrich_cve(
        self,
        cve_id: str,
        *,
        parent_run_id: str | None = None,
    ) -> list[NormalizationResult]:
        async with self._session_factory() as session:
            view = await get_vulnerability_by_cve(session, cve_id)
        if view is None:
            raise LookupError(f"vulnerability not found: {cve_id}")

        results: list[NormalizationResult] = []
        for job in self._planner.plan(view, cve_id):
            source = self._sources[job.source_id]
            adapter = self._adapters[job.source_id]
            envelopes = await self._acquisition.query(
                source,
                adapter,
                job.query,
                parent_run_id=parent_run_id,
            )
            mapper = self._mappers[source.adapter_type]
            for envelope in envelopes:
                candidate = mapper.map(envelope)
                async with self._session_factory() as session, session.begin():
                    observation = await self._evidence_ingress.accept(session, source, envelope)
                    result = await self._writer.apply(
                        session,
                        root_object_id=view.object_id,
                        source=source,
                        observation=observation,
                        candidate=candidate,
                        processor_name=mapper.PROCESSOR_NAME,
                        processor_version=mapper.PROCESSOR_VERSION,
                    )
                results.append(result)
        return results
