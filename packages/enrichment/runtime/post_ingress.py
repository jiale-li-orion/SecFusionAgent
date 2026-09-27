from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.enrichment.assets.cpe_join import AssetCPEApplicabilityJoinService
from packages.enrichment.assets.internetdb import ShodanInternetDBAssetMapper
from packages.enrichment.assets.service import map_asset_observation
from packages.enrichment.processors.cisa_kev import CISAKEVMapper
from packages.enrichment.processors.cnnvd import CNNVDMapper
from packages.enrichment.processors.cnvd import CNVDHTMLMapper
from packages.enrichment.processors.epss import FIRSTEPSSMapper
from packages.enrichment.processors.github_advisory import GitHubAdvisoryMapper
from packages.enrichment.processors.osv import OSVMapper
from packages.enrichment.research.exact_cve import ExactCVEResearchBridge
from packages.intelligence.documents.parsers import (
    HTMLDocumentParser,
    PDFDocumentParser,
    PlainTextDocumentParser,
)
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.incident.ingress import IncidentSignalIngress
from packages.intelligence.incident.promotion import (
    IncidentNotPromotable,
    IncidentPromotionService,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.ingestion.replay import ObservationEnvelopeLoader, ObservationReplay
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    EnrichmentMapper,
    ObjectCandidate,
)
from packages.intelligence.knowledge.identity import canonical_cve_id, cve_canonical_key
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.factory import create_durable_bug_normalizer
from packages.intelligence.storage.artifacts import ArtifactStore
from packages.intelligence.storage.knowledge_models import ExternalIdentifierModel
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.sources.contracts import RetentionMode, SourceDefinition
from packages.sources.errors import SourceSchemaChanged


class PostIngressStatus(StrEnum):
    PROCESSED = "processed"
    REPLAY = "replay"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class PostIngressResult(BaseModel):
    observation_id: str
    source_id: str
    handler: str
    status: PostIngressStatus
    metadata_complete: bool
    output_refs: dict[str, object] = Field(default_factory=dict)
    detail: str | None = None


class ObservationProcessingRuntime:
    """Route already-fixed Evidence into the M3 processor owned by its source contract.

    The runtime deliberately starts from Observation rather than a live adapter.
    This makes manual seeds, crash recovery, benchmark replay, and processor-version
    migrations use the same post-ingress path.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore,
        *,
        incident_ingress: IncidentSignalIngress | None = None,
        incident_promotion: IncidentPromotionService | None = None,
        source_definitions: Mapping[str, SourceDefinition] | None = None,
    ) -> None:
        self._loader = ObservationEnvelopeLoader(artifact_store)
        self._evidence_ingress = EvidenceIngress(artifact_store)
        self._writer = EvidenceBackedKnowledgeWriter()
        self._research_exact_cve = ExactCVEResearchBridge(self._writer)
        self._managed = ManagedDocumentService(
            self._evidence_ingress,
            {
                "application/pdf": PDFDocumentParser(),
                "text/plain": PlainTextDocumentParser(),
                "text/yaml": PlainTextDocumentParser(),
                "application/yaml": PlainTextDocumentParser(),
                "application/x-yaml": PlainTextDocumentParser(),
                "application/octet-stream": PlainTextDocumentParser(),
                "text/html": HTMLDocumentParser(),
                "application/xhtml+xml": HTMLDocumentParser(),
            },
        )
        self._structured = StructuredIndexService(
            self._evidence_ingress,
            self._writer,
            {"github_repo": GitHubRepoMapper()},
        )
        self._time_bounded_mappers: dict[str, EnrichmentMapper] = {
            "osv": OSVMapper(),
            "github_global_advisory": GitHubAdvisoryMapper(),
            "cisa_kev": CISAKEVMapper(),
            "first_epss": FIRSTEPSSMapper(),
            "cnvd": CNVDHTMLMapper(),
            "cnnvd": CNNVDMapper(),
        }
        self._asset_mappers: dict[str, EnrichmentMapper] = {
            "shodan_internetdb": ShodanInternetDBAssetMapper(),
        }
        self._asset_cpe_join = AssetCPEApplicabilityJoinService(self._writer)
        self._incident_ingress = incident_ingress
        self._incident_promotion = incident_promotion
        self._source_definitions = dict(source_definitions or {})

    async def process(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        observation_id: str,
    ) -> PostIngressResult:
        replay = await self._loader.load(session, observation_id)
        envelope = replay.envelope
        if envelope.source_id != source.source_id:
            raise ValueError("observation source does not match source definition")

        try:
            if source.retention_mode is RetentionMode.DURABLE_MANAGED:
                managed_result = await self._managed.ingest(session, source, envelope)
                output_refs: dict[str, object] = {
                    "object_id": managed_result.object_id,
                    "document_id": managed_result.document_id,
                    "document_revision_id": managed_result.document_revision_id,
                    "chunk_count": managed_result.chunk_count,
                }
                if source.source_class == "research_insight":
                    exact_result = await self._research_exact_cve.enrich_document_revision(
                        session,
                        source=source,
                        replay=replay,
                        root_object_id=managed_result.object_id,
                        document_revision_id=managed_result.document_revision_id,
                    )
                    output_refs.update(
                        {
                            "research_exact_cve_knowledge_revision": (
                                exact_result.knowledge_revision
                            ),
                            "research_exact_cve_relation_ids": exact_result.relation_ids,
                        }
                    )
                return PostIngressResult(
                    observation_id=observation_id,
                    source_id=source.source_id,
                    handler="managed_document",
                    status=(
                        PostIngressStatus.REPLAY
                        if managed_result.replay
                        else PostIngressStatus.PROCESSED
                    ),
                    metadata_complete=replay.metadata_complete,
                    output_refs=output_refs,
                )

            if source.retention_mode is RetentionMode.SELECTIVE_INDEX:
                structured_result = await self._structured.ingest(session, source, envelope)
                return PostIngressResult(
                    observation_id=observation_id,
                    source_id=source.source_id,
                    handler="structured_index",
                    status=(
                        PostIngressStatus.REPLAY
                        if structured_result.replay
                        else PostIngressStatus.PROCESSED
                    ),
                    metadata_complete=replay.metadata_complete,
                    output_refs={
                        "knowledge_revision": structured_result.normalization.knowledge_revision,
                        "object_ids": structured_result.normalization.object_ids,
                        "relation_ids": structured_result.normalization.relation_ids,
                    },
                )

            if source.retention_mode is RetentionMode.HOT_WINDOW:
                ack = await self._evidence_ingress.accept(session, source, envelope)
                normalizer = create_durable_bug_normalizer(source)
                normalization_result = await normalizer.normalize(session, source, envelope, ack)
                return PostIngressResult(
                    observation_id=observation_id,
                    source_id=source.source_id,
                    handler="canonical_bug",
                    status=PostIngressStatus.PROCESSED,
                    metadata_complete=replay.metadata_complete,
                    output_refs={
                        "knowledge_revision": normalization_result.knowledge_revision,
                        "object_ids": normalization_result.object_ids,
                        "claim_ids": normalization_result.claim_ids,
                    },
                )

            if source.retention_mode is RetentionMode.TIME_BOUNDED:
                if source.source_class == "internet_asset_intelligence":
                    asset = map_asset_observation(envelope)
                    mapper = self._asset_mappers.get(source.adapter_type)
                    if mapper is not None and asset.vulnerabilities:
                        ack = await self._evidence_ingress.accept(session, source, envelope)
                        candidate = mapper.map(envelope)
                        normalization = await self._writer.apply(
                            session,
                            source=source,
                            observation=ack,
                            candidate=candidate,
                            processor_name=mapper.PROCESSOR_NAME,
                            processor_version=mapper.PROCESSOR_VERSION,
                        )
                        return PostIngressResult(
                            observation_id=observation_id,
                            source_id=source.source_id,
                            handler="asset_vulnerability_association",
                            status=PostIngressStatus.PROCESSED,
                            metadata_complete=replay.metadata_complete,
                            output_refs={
                                "ip": asset.ip,
                                "vulnerabilities": asset.vulnerabilities,
                                "knowledge_revision": normalization.knowledge_revision,
                                "object_ids": normalization.object_ids,
                                "relation_ids": normalization.relation_ids,
                            },
                        )
                    if source.adapter_type == "shodan" and asset.provider == "shodan" and asset.cpe:
                        ack = await self._evidence_ingress.accept(session, source, envelope)
                        join_result = await self._asset_cpe_join.enrich(
                            session,
                            source=source,
                            envelope=envelope,
                            observation=ack,
                        )
                        if join_result is not None:
                            return PostIngressResult(
                                observation_id=observation_id,
                                source_id=source.source_id,
                                handler="asset_cpe_applicability_join",
                                status=PostIngressStatus.PROCESSED,
                                metadata_complete=replay.metadata_complete,
                                output_refs={
                                    "ip": asset.ip,
                                    "port": asset.port,
                                    "cpe": asset.cpe,
                                    "knowledge_revision": join_result.knowledge_revision,
                                    "object_ids": join_result.object_ids,
                                    "relation_ids": join_result.relation_ids,
                                },
                            )
                    return PostIngressResult(
                        observation_id=observation_id,
                        source_id=source.source_id,
                        handler="asset_observation",
                        status=PostIngressStatus.PROCESSED,
                        metadata_complete=replay.metadata_complete,
                        output_refs={
                            "ip": asset.ip,
                            "port": asset.port,
                            "product": asset.product,
                            "version": asset.version,
                            "vulnerabilities": asset.vulnerabilities,
                            "relation_context": asset.relation_context,
                        },
                        detail=(
                            "typed time-bounded observation only; "
                            "no durable InternetAsset/affectedness promotion performed"
                        ),
                    )
                mapper = self._time_bounded_mappers.get(source.adapter_type)
                if mapper is None:
                    return self._skipped(replay, source, "no time-bounded mapper registered")
                ack = await self._evidence_ingress.accept(session, source, envelope)
                candidate = mapper.map(envelope)
                candidate, root_object_id = await _bind_enrichment_root(session, candidate)
                enrichment_result = await self._writer.apply(
                    session,
                    root_object_id=root_object_id,
                    source=source,
                    observation=ack,
                    candidate=candidate,
                    processor_name=mapper.PROCESSOR_NAME,
                    processor_version=mapper.PROCESSOR_VERSION,
                )
                return PostIngressResult(
                    observation_id=observation_id,
                    source_id=source.source_id,
                    handler="time_bounded_enrichment",
                    status=PostIngressStatus.PROCESSED,
                    metadata_complete=replay.metadata_complete,
                    output_refs={
                        "knowledge_revision": enrichment_result.knowledge_revision,
                        "object_ids": enrichment_result.object_ids,
                        "claim_ids": enrichment_result.claim_ids,
                        "relation_ids": enrichment_result.relation_ids,
                    },
                )

            if source.retention_mode is RetentionMode.INCIDENT_SIGNAL:
                if self._incident_ingress is None:
                    return self._blocked(replay, source, "incident runtime is not configured")
                signal = await self._incident_ingress.accept(source, envelope)
                output: dict[str, object] = {
                    "signal_id": signal.signal_id,
                    "incident_candidate_id": signal.incident_candidate_id,
                    "material_change": signal.material_change,
                }
                status = PostIngressStatus.CANDIDATE
                detail = "incident signal correlated; candidate not promoted"
                if self._incident_promotion is not None and self._source_definitions:
                    try:
                        promoted = await self._incident_promotion.promote(
                            session,
                            candidate_id=signal.incident_candidate_id,
                            sources=self._source_definitions,
                        )
                    except IncidentNotPromotable:
                        pass
                    else:
                        status = PostIngressStatus.PROCESSED
                        detail = "incident candidate promoted"
                        output.update(
                            {
                                "incident_id": promoted.incident_id,
                                "incident_revision": promoted.incident_revision,
                            }
                        )
                return PostIngressResult(
                    observation_id=observation_id,
                    source_id=source.source_id,
                    handler="incident_signal",
                    status=status,
                    metadata_complete=replay.metadata_complete,
                    output_refs=output,
                    detail=detail,
                )

            return self._skipped(replay, source, "retention mode has no post-ingress handler")
        except (LookupError, SourceSchemaChanged, ValueError) as exc:
            detail = str(exc)
            if not replay.metadata_complete:
                detail = f"historical request metadata missing; {detail}"
            return self._blocked(replay, source, detail)

    @staticmethod
    def _blocked(
        replay: ObservationReplay, source: SourceDefinition, detail: str
    ) -> PostIngressResult:
        return PostIngressResult(
            observation_id=replay.observation_id,
            source_id=source.source_id,
            handler="blocked",
            status=PostIngressStatus.BLOCKED,
            metadata_complete=replay.metadata_complete,
            detail=detail,
        )

    @staticmethod
    def _skipped(
        replay: ObservationReplay, source: SourceDefinition, detail: str
    ) -> PostIngressResult:
        return PostIngressResult(
            observation_id=replay.observation_id,
            source_id=source.source_id,
            handler="unhandled",
            status=PostIngressStatus.SKIPPED,
            metadata_complete=replay.metadata_complete,
            detail=detail,
        )


async def _bind_enrichment_root(
    session: AsyncSession, candidate: EnrichmentCandidate
) -> tuple[EnrichmentCandidate, str | None]:
    if candidate.root_object is not None:
        return candidate, None

    object_ids: set[str] = set()
    for namespace, values in candidate.root_identifiers.items():
        for value in values:
            row = await session.scalar(
                select(ExternalIdentifierModel).where(
                    ExternalIdentifierModel.namespace == namespace,
                    ExternalIdentifierModel.value == value,
                )
            )
            if row is not None:
                object_ids.add(row.object_id)

    if len(object_ids) == 1:
        return candidate, next(iter(object_ids))
    if len(object_ids) > 1:
        raise ValueError(
            f"enrichment identifiers resolve to multiple root objects: {sorted(object_ids)}"
        )

    cve_values = {canonical_cve_id(value) for value in candidate.root_identifiers.get("cve", [])}
    if len(cve_values) == 1:
        cve_id = next(iter(cve_values))
        seeded = candidate.model_copy(
            update={
                "root_object": ObjectCandidate(
                    object_type="Vulnerability",
                    canonical_key=cve_canonical_key(cve_id),
                    properties={"display_name": cve_id},
                )
            }
        )
        return seeded, None

    raise LookupError(
        "no existing root object matches enrichment identifiers and no unique strong CVE "
        "identifier is available for canonical root seeding"
    )
