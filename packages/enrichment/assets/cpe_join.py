from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast
from urllib.parse import unquote
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from packages.enrichment.assets.service import map_asset_observation
from packages.intelligence.ingestion.evidence import ObservationAck
from packages.intelligence.knowledge.contracts import (
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.identity import cpe_product_canonical_key
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.canonical import NormalizationResult
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.sources.contracts import IngestEnvelope, SourceDefinition

SOURCE_SEMANTICS = "nvd_cpe_asset_join"
_PRODUCT_IDENTITY = "cpe23_product"
_NUMERIC_VERSION = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class ParsedCPE:
    raw: str
    part: str
    vendor: str
    product: str
    version: str

    @property
    def product_key(self) -> str:
        return cpe_product_canonical_key(self.part, self.vendor, self.product)

    @property
    def software_version_key(self) -> str | None:
        if self.version in {"", "*", "-"}:
            return None
        digest = sha256(
            f"{self.part}|{self.vendor}|{self.product}|{self.version}".encode()
        ).hexdigest()
        return f"software-version:cpe-sha256:{digest}"


@dataclass(frozen=True)
class _JoinMatch:
    vulnerability: ObjectModel
    relation: RelationModel
    matched_cpes: tuple[str, ...]


class AssetCPEApplicabilityJoinService:
    """Derive asset affectedness only when a full NVD CPE configuration matches."""

    PROCESSOR_NAME = "asset-nvd-cpe-applicability-join"
    PROCESSOR_VERSION = "1"

    def __init__(self, writer: EvidenceBackedKnowledgeWriter) -> None:
        self._writer = writer

    async def enrich(
        self,
        session: AsyncSession,
        *,
        source: SourceDefinition,
        envelope: IngestEnvelope,
        observation: ObservationAck,
    ) -> NormalizationResult | None:
        asset = map_asset_observation(envelope)
        parsed = _asset_cpes(asset.cpe, fallback_version=asset.version)
        if not parsed:
            return None
        matches = await _find_matches(session, parsed)
        candidate = _candidate_for_asset(envelope, parsed, matches)
        result = await self._writer.apply(
            session,
            source=source,
            observation=observation,
            candidate=candidate,
            processor_name=self.PROCESSOR_NAME,
            processor_version=self.PROCESSOR_VERSION,
            origin="deterministic_derived",
        )
        await _copy_support_evidence(session, candidate, result)
        return result


def parse_cpe(value: str) -> ParsedCPE | None:
    if value.startswith("cpe:2.3:"):
        parts = _split_escaped(value)
        if len(parts) < 6:
            return None
        part, vendor, product, version = parts[2], parts[3], parts[4], parts[5]
    elif value.startswith("cpe:/"):
        parts = value[5:].split(":")
        if len(parts) < 3:
            return None
        part, vendor, product = parts[0], parts[1], parts[2]
        version = parts[3] if len(parts) > 3 else "*"
    else:
        return None
    if any(item in {"", "*", "-"} for item in (part, vendor, product)):
        return None
    return ParsedCPE(
        raw=value,
        part=unquote(part).lower(),
        vendor=unquote(vendor).lower(),
        product=unquote(product).lower(),
        version=unquote(version),
    )


def configuration_matches(root: dict[str, Any], asset_cpes: tuple[ParsedCPE, ...]) -> bool:
    operands: list[bool] = []
    matches = root.get("cpeMatch")
    if isinstance(matches, list):
        operands.extend(
            _cpe_match_satisfied(item, asset_cpes) for item in matches if isinstance(item, dict)
        )
    nodes = root.get("nodes")
    if isinstance(nodes, list):
        operands.extend(
            configuration_matches(node, asset_cpes) for node in nodes if isinstance(node, dict)
        )
    if not operands:
        return False
    operator = root.get("operator")
    value = all(operands) if operator == "AND" else any(operands)
    return not value if root.get("negate") is True else value


def _asset_cpes(values: list[str], *, fallback_version: str | None) -> tuple[ParsedCPE, ...]:
    parsed: list[ParsedCPE] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in values:
        item = parse_cpe(raw)
        if item is None:
            continue
        if item.version in {"", "*"} and fallback_version:
            item = ParsedCPE(
                raw=item.raw,
                part=item.part,
                vendor=item.vendor,
                product=item.product,
                version=fallback_version,
            )
        key = (item.part, item.vendor, item.product, item.version)
        if key not in seen:
            seen.add(key)
            parsed.append(item)
    return tuple(parsed)


async def _find_matches(
    session: AsyncSession,
    asset_cpes: tuple[ParsedCPE, ...],
) -> list[_JoinMatch]:
    product_keys = {item.product_key for item in asset_cpes}
    target = aliased(ObjectModel)
    vulnerability = aliased(ObjectModel)
    rows = (
        await session.execute(
            select(RelationModel, target, vulnerability)
            .join(target, target.object_id == RelationModel.target_object_id)
            .join(vulnerability, vulnerability.object_id == RelationModel.source_object_id)
            .where(
                RelationModel.relation_type == "applicability-status",
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
                target.object_type == "Product",
                vulnerability.object_type == "Vulnerability",
            )
        )
    ).all()
    result: list[_JoinMatch] = []
    for relation, product, vuln in rows:
        if product.canonical_key not in product_keys:
            continue
        if relation.qualifier.get("source_semantics") != "nvd_cpe":
            continue
        platform = relation.qualifier.get("platform")
        configuration = relation.qualifier.get("configuration")
        if not isinstance(platform, str) or not isinstance(configuration, dict):
            continue
        root_snapshot = configuration.get("root_snapshot")
        if not isinstance(root_snapshot, dict):
            continue
        target_match = {
            "criteria": platform,
            **_dict_value(relation.qualifier.get("version_range")),
        }
        matched = tuple(item.raw for item in asset_cpes if _single_cpe_matches(target_match, item))
        if not matched or not configuration_matches(root_snapshot, asset_cpes):
            continue
        result.append(_JoinMatch(vulnerability=vuln, relation=relation, matched_cpes=matched))
    return result


def _candidate_for_asset(
    envelope: IngestEnvelope,
    parsed: tuple[ParsedCPE, ...],
    matches: list[_JoinMatch],
) -> EnrichmentCandidate:
    asset = map_asset_observation(envelope)
    root_key = f"internet-asset:service:{asset.ip}:{asset.port}/{asset.transport}"
    relations: list[RelationCandidate] = []
    seen_products: set[str] = set()
    seen_versions: set[str] = set()
    for index, item in enumerate(parsed):
        product_properties: dict[str, JsonValue] = {
            "identity_scheme": _PRODUCT_IDENTITY,
            "cpe_part": item.part,
            "vendor": item.vendor,
            "product": item.product,
        }
        if item.product_key not in seen_products:
            seen_products.add(item.product_key)
            relations.append(
                RelationCandidate(
                    relation_type="asset-runs-product",
                    target=ObjectCandidate(
                        object_type="Product",
                        canonical_key=item.product_key,
                        properties=product_properties,
                    ),
                    qualifier={
                        "source_semantics": "asset_cpe",
                        "asset_cpe": item.raw,
                        "observed_at": envelope.observed_at.isoformat(),
                    },
                    locator={"kind": "jsonpath", "path": f"$.cpe[{index}]"},
                )
            )
        version_key = item.software_version_key
        if version_key is not None and version_key not in seen_versions:
            seen_versions.add(version_key)
            relations.append(
                RelationCandidate(
                    relation_type="asset-version",
                    target=ObjectCandidate(
                        object_type="SoftwareVersion",
                        canonical_key=version_key,
                        properties={
                            **product_properties,
                            "version": item.version,
                        },
                    ),
                    qualifier={
                        "source_semantics": "asset_cpe",
                        "asset_cpe": item.raw,
                        "observed_at": envelope.observed_at.isoformat(),
                    },
                    locator={"kind": "jsonpath", "path": f"$.cpe[{index}]"},
                )
            )

    by_vulnerability: dict[str, list[_JoinMatch]] = {}
    for match in matches:
        by_vulnerability.setdefault(match.vulnerability.object_id, []).append(match)
    for vuln_matches in by_vulnerability.values():
        vulnerability = vuln_matches[0].vulnerability
        cve_id = _cve_from_key(vulnerability.canonical_key)
        relations.append(
            RelationCandidate(
                relation_type="asset-potentially-affected",
                target=ObjectCandidate(
                    object_type="Vulnerability",
                    canonical_key=vulnerability.canonical_key,
                    properties=cast(dict[str, JsonValue], dict(vulnerability.properties)),
                    identifiers={"cve": [cve_id]} if cve_id is not None else {},
                ),
                qualifier={
                    "source_semantics": SOURCE_SEMANTICS,
                    "asset_cpes": cast(
                        list[JsonValue],
                        sorted({cpe for item in vuln_matches for cpe in item.matched_cpes}),
                    ),
                    "support_relation_ids": cast(
                        list[JsonValue],
                        sorted({item.relation.relation_id for item in vuln_matches}),
                    ),
                    "observed_at": envelope.observed_at.isoformat(),
                    "asset_port": asset.port,
                    "transport": asset.transport,
                },
                locator={"kind": "jsonpath", "path": "$.cpe"},
            )
        )

    return EnrichmentCandidate(
        root_object=ObjectCandidate(
            object_type="InternetAsset",
            canonical_key=root_key,
            properties={
                "ip": asset.ip,
                "port": asset.port,
                "transport": asset.transport,
            },
            identifiers={"internet_service": [f"{asset.ip}:{asset.port}/{asset.transport}"]},
        ),
        relations=relations,
        replace_relation_types=[
            "asset-runs-product",
            "asset-version",
            "asset-potentially-affected",
        ],
    )


async def _copy_support_evidence(
    session: AsyncSession,
    candidate: EnrichmentCandidate,
    result: NormalizationResult,
) -> None:
    for relation_candidate, relation_id in zip(
        candidate.relations,
        result.relation_ids,
        strict=True,
    ):
        if relation_candidate.relation_type != "asset-potentially-affected":
            continue
        support_ids = relation_candidate.qualifier.get("support_relation_ids")
        if not isinstance(support_ids, list):
            continue
        for support_id in support_ids:
            if not isinstance(support_id, str):
                continue
            links = list(
                await session.scalars(
                    select(EvidenceLinkModel).where(
                        EvidenceLinkModel.target_kind == "relation",
                        EvidenceLinkModel.target_id == support_id,
                    )
                )
            )
            for link in links:
                locator_hash = _json_hash(link.locator)
                evidence_link_id = _stable_id(
                    f"evidence-link:relation:{relation_id}:{link.observation_id}:{locator_hash}"
                )
                if await session.get(EvidenceLinkModel, evidence_link_id) is not None:
                    continue
                session.add(
                    EvidenceLinkModel(
                        evidence_link_id=evidence_link_id,
                        target_kind="relation",
                        target_id=relation_id,
                        observation_id=link.observation_id,
                        artifact_id=link.artifact_id,
                        locator=link.locator,
                        locator_hash=locator_hash,
                    )
                )


def _cpe_match_satisfied(match: dict[str, Any], asset_cpes: tuple[ParsedCPE, ...]) -> bool:
    return any(_single_cpe_matches(match, item) for item in asset_cpes)


def _single_cpe_matches(match: dict[str, Any], asset: ParsedCPE) -> bool:
    criteria = match.get("criteria")
    if not isinstance(criteria, str):
        return False
    required = parse_cpe(criteria)
    if required is None:
        return False
    if (required.part, required.vendor, required.product) != (
        asset.part,
        asset.vendor,
        asset.product,
    ):
        return False
    if required.version not in {"*", "-", ""} and required.version != asset.version:
        return False
    if required.version == "-" and asset.version != "-":
        return False
    return _version_in_bounds(asset.version, match)


def _version_in_bounds(version: str, match: dict[str, Any]) -> bool:
    bounds = {
        key: value
        for key in (
            "versionStartIncluding",
            "versionStartExcluding",
            "versionEndIncluding",
            "versionEndExcluding",
        )
        if isinstance((value := match.get(key)), str) and value
    }
    if not bounds:
        return True
    current = _numeric_version(version)
    if current is None:
        return False
    for key, raw_bound in bounds.items():
        bound = _numeric_version(raw_bound)
        if bound is None:
            return False
        comparison = _compare_versions(current, bound)
        if key == "versionStartIncluding" and comparison < 0:
            return False
        if key == "versionStartExcluding" and comparison <= 0:
            return False
        if key == "versionEndIncluding" and comparison > 0:
            return False
        if key == "versionEndExcluding" and comparison >= 0:
            return False
    return True


def _numeric_version(value: str) -> tuple[int, ...] | None:
    normalized = value.strip().removeprefix("v")
    if _NUMERIC_VERSION.fullmatch(normalized) is None:
        return None
    return tuple(int(part) for part in normalized.split("."))


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    return (padded_left > padded_right) - (padded_left < padded_right)


def _split_escaped(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == ":":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current))
    return parts


def _dict_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _cve_from_key(value: str) -> str | None:
    if not value.startswith("cve:CVE-"):
        return None
    return value.removeprefix("cve:")


def _json_hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
