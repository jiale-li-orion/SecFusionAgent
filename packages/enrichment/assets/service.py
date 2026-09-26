from __future__ import annotations

from ipaddress import ip_address
from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.assets.contracts import AssetObservation, AssetObservationResult
from packages.intelligence.ingestion.evidence import EvidenceIngress, ObservationAck
from packages.monitoring.acquisition.service import AcquisitionService
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    QuerySpec,
    SourceAdapter,
    SourceDefinition,
)


class AssetObservationService:
    """M3 time-bounded asset lookup with explicit durable promotion."""

    def __init__(self, acquisition: AcquisitionService, evidence_ingress: EvidenceIngress) -> None:
        self._acquisition = acquisition
        self._evidence_ingress = evidence_ingress

    async def query(
        self,
        source: SourceDefinition,
        adapter: SourceAdapter,
        spec: QuerySpec,
        *,
        parent_run_id: str | None,
        trigger: AcquisitionTrigger = AcquisitionTrigger.INVESTIGATION,
    ) -> list[AssetObservationResult]:
        envelopes = await self._acquisition.query(
            source,
            adapter,
            spec,
            parent_run_id=parent_run_id,
            trigger=trigger,
        )
        return [
            AssetObservationResult(
                observation=_map_asset_observation(envelope),
                envelope=envelope,
            )
            for envelope in envelopes
        ]

    async def promote(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        result: AssetObservationResult,
    ) -> ObservationAck:
        return await self._evidence_ingress.accept(session, source, result.envelope)


def _map_asset_observation(envelope: IngestEnvelope) -> AssetObservation:
    payload = envelope.json_payload
    ip_value = payload.get("ip")
    if isinstance(ip_value, int) and not isinstance(ip_value, bool):
        ip_value = str(ip_address(ip_value))
    if not isinstance(ip_value, str) or not ip_value:
        raise ValueError("asset observation requires normalized ip")
    port = payload.get("port")
    if not isinstance(port, int) or isinstance(port, bool):
        raise ValueError("asset observation requires integer port")
    transport = payload.get("transport")
    if not isinstance(transport, str) or not transport:
        transport = "tcp"
    query = envelope.request_metadata.get("query")
    if not isinstance(query, str):
        raise ValueError("asset observation envelope has no query provenance")
    provider = envelope.request_metadata.get("provider")
    if not isinstance(provider, str):
        raise ValueError("asset observation envelope has no provider provenance")
    return AssetObservation(
        source_id=envelope.source_id,
        provider=provider,
        acquisition_run_id=envelope.acquisition_run_id,
        query=query,
        observed_at=envelope.observed_at,
        external_object_id=envelope.external_object_id,
        external_revision=envelope.external_revision,
        ip=ip_value,
        port=port,
        transport=transport.lower(),
        hostnames=_string_list(payload.get("hostnames")),
        domains=_string_list(payload.get("domains")),
        product=_optional_string(payload.get("product")),
        version=_optional_string(payload.get("version")),
        organization=_optional_string(payload.get("org")),
        isp=_optional_string(payload.get("isp")),
        asn=_optional_string(payload.get("asn")),
        cpe=_string_list(payload.get("cpe")),
        location=_json_object(payload.get("location")),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _json_object(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, JsonValue], value)
