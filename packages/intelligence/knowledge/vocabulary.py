from __future__ import annotations

from collections.abc import Collection
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.intelligence.knowledge.contracts import KnowledgeOrigin

VOCABULARY_REVISION = "enrichment-v1"


class EnrichmentDimension(StrEnum):
    IDENTITY = "identity"
    SEVERITY = "severity"
    WEAKNESS = "weakness"
    PRODUCT_PACKAGE = "product_package"
    VERSION_APPLICABILITY = "version_applicability"
    FIX_REMEDIATION = "fix_remediation"
    EXPLOIT_STATE = "exploit_state"
    EXPLOIT_LIKELIHOOD = "exploit_likelihood"
    ADVISORY_REFERENCE = "advisory_reference"
    ASSET_EXPOSURE = "asset_exposure"
    RESEARCH_PAPER = "research_paper"
    INCIDENT_CONTEXT = "incident_context"


class VocabularyScope(StrEnum):
    CANONICAL = "canonical"
    SOURCE_SPECIFIC = "source_specific"
    EXPLORATORY = "exploratory"
    UNREGISTERED = "unregistered"


class ApplicabilityState(StrEnum):
    AFFECTED = "affected"
    NOT_AFFECTED = "not_affected"
    FIXED = "fixed"
    UNDER_INVESTIGATION = "under_investigation"
    UNKNOWN = "unknown"


class VocabularyTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: Literal["claim", "relation"]
    dimension: EnrichmentDimension
    benchmarked: bool = True
    subject_types: tuple[str, ...] = ()
    target_types: tuple[str, ...] = ()
    required_qualifier_keys: tuple[str, ...] = ()


def _claim(
    name: str,
    dimension: EnrichmentDimension,
    *,
    benchmarked: bool = True,
    subject_types: tuple[str, ...] = (),
    required_qualifier_keys: tuple[str, ...] = (),
) -> VocabularyTerm:
    return VocabularyTerm(
        name=name,
        kind="claim",
        dimension=dimension,
        benchmarked=benchmarked,
        subject_types=subject_types,
        required_qualifier_keys=required_qualifier_keys,
    )


def _relation(
    name: str,
    dimension: EnrichmentDimension,
    *,
    benchmarked: bool = True,
    subject_types: tuple[str, ...] = (),
    target_types: tuple[str, ...] = (),
    required_qualifier_keys: tuple[str, ...] = (),
) -> VocabularyTerm:
    return VocabularyTerm(
        name=name,
        kind="relation",
        dimension=dimension,
        benchmarked=benchmarked,
        subject_types=subject_types,
        target_types=target_types,
        required_qualifier_keys=required_qualifier_keys,
    )


CANONICAL_TERMS: tuple[VocabularyTerm, ...] = (
    # Identity stays a normalization diagnostic and is not part of competition enrichment P/R.
    _claim(
        "external-identifier",
        EnrichmentDimension.IDENTITY,
        benchmarked=False,
    ),
    # Severity / weakness on a vulnerability.
    _claim("cvss_score", EnrichmentDimension.SEVERITY, subject_types=("Vulnerability",)),
    _claim("cvss_vector", EnrichmentDimension.SEVERITY, subject_types=("Vulnerability",)),
    _claim("cvss_version", EnrichmentDimension.SEVERITY, subject_types=("Vulnerability",)),
    _claim("cvss_severity", EnrichmentDimension.SEVERITY, subject_types=("Vulnerability",)),
    _relation(
        "has-weakness",
        EnrichmentDimension.WEAKNESS,
        subject_types=("Vulnerability",),
        target_types=("Weakness",),
    ),
    # Product / version applicability.
    _relation(
        "affects-package",
        EnrichmentDimension.PRODUCT_PACKAGE,
        subject_types=("Vulnerability",),
        target_types=("Package",),
    ),
    _relation(
        "affects-product",
        EnrichmentDimension.PRODUCT_PACKAGE,
        subject_types=("Vulnerability",),
        target_types=("Product",),
    ),
    _relation(
        "applicability-status",
        EnrichmentDimension.VERSION_APPLICABILITY,
        subject_types=("Vulnerability",),
        target_types=("Product", "Package", "SoftwareVersion"),
        required_qualifier_keys=("state", "source_semantics"),
    ),
    # Fix / remediation. Internal repository graph edges are canonical but are not benchmark facts.
    _relation(
        "fixed-by",
        EnrichmentDimension.FIX_REMEDIATION,
        subject_types=("Vulnerability",),
        target_types=("Commit",),
    ),
    _relation(
        "fixed-version",
        EnrichmentDimension.FIX_REMEDIATION,
        subject_types=("Vulnerability",),
        target_types=("SoftwareVersion",),
    ),
    _relation(
        "release-contains-commit",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Release",),
        target_types=("Commit",),
    ),
    _relation(
        "belongs-to-repo",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Issue", "PullRequest", "Commit", "Release"),
        target_types=("Repo",),
    ),
    _relation(
        "merged-as",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("PullRequest",),
        target_types=("Commit",),
    ),
    _relation(
        "head-commit",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("PullRequest",),
        target_types=("Commit",),
    ),
    _relation(
        "has-parent-commit",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Commit",),
        target_types=("Commit",),
    ),
    _relation(
        "references-development-object",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Vulnerability",),
        target_types=("Issue", "PullRequest", "Commit", "Release"),
    ),
    _claim(
        "workaround",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Vulnerability",),
    ),
    _claim(
        "mitigation",
        EnrichmentDimension.FIX_REMEDIATION,
        benchmarked=False,
        subject_types=("Vulnerability",),
    ),
    # Exploitation. PoC availability is a derived convenience field; has-poc is the benchmark edge.
    _claim(
        "known_exploited",
        EnrichmentDimension.EXPLOIT_STATE,
        subject_types=("Vulnerability",),
    ),
    _claim(
        "poc_available",
        EnrichmentDimension.EXPLOIT_STATE,
        benchmarked=False,
        subject_types=("Vulnerability",),
    ),
    _relation(
        "has-poc",
        EnrichmentDimension.EXPLOIT_STATE,
        subject_types=("Vulnerability",),
        target_types=("ExploitArtifact",),
    ),
    _claim(
        "exploit_maturity",
        EnrichmentDimension.EXPLOIT_STATE,
        subject_types=("Vulnerability",),
    ),
    _claim(
        "attack_condition",
        EnrichmentDimension.EXPLOIT_STATE,
        benchmarked=False,
        subject_types=("Vulnerability",),
    ),
    _claim(
        "epss_probability",
        EnrichmentDimension.EXPLOIT_LIKELIHOOD,
        subject_types=("Vulnerability",),
    ),
    _claim(
        "epss_percentile",
        EnrichmentDimension.EXPLOIT_LIKELIHOOD,
        subject_types=("Vulnerability",),
    ),
    # Advisory / source relations.
    _relation(
        "described-by",
        EnrichmentDimension.ADVISORY_REFERENCE,
        subject_types=("Vulnerability",),
        target_types=("Document",),
    ),
    _relation(
        "vendor-advisory",
        EnrichmentDimension.ADVISORY_REFERENCE,
        subject_types=("Vulnerability",),
        target_types=("Document",),
    ),
    # Time-bounded asset observations.
    _relation(
        "asset-runs-product",
        EnrichmentDimension.ASSET_EXPOSURE,
        benchmarked=False,
        subject_types=("InternetAsset",),
        target_types=("Product",),
    ),
    _relation(
        "asset-version",
        EnrichmentDimension.ASSET_EXPOSURE,
        benchmarked=False,
        subject_types=("InternetAsset",),
        target_types=("SoftwareVersion",),
    ),
    _relation(
        "asset-potentially-affected",
        EnrichmentDimension.ASSET_EXPOSURE,
        subject_types=("InternetAsset",),
        target_types=("Vulnerability",),
    ),
    # Research association. Only the stable paper↔vulnerability edge is benchmarked in v1.
    _relation(
        "discusses-vulnerability",
        EnrichmentDimension.RESEARCH_PAPER,
        subject_types=("ResearchWork", "Document"),
        target_types=("Vulnerability",),
    ),
    _relation(
        "evaluates-attack",
        EnrichmentDimension.RESEARCH_PAPER,
        benchmarked=False,
        subject_types=("ResearchWork", "Document"),
    ),
    _relation(
        "evaluates-defense",
        EnrichmentDimension.RESEARCH_PAPER,
        benchmarked=False,
        subject_types=("ResearchWork", "Document"),
    ),
    _relation(
        "supports",
        EnrichmentDimension.RESEARCH_PAPER,
        benchmarked=False,
        subject_types=("ResearchWork", "Document"),
    ),
    _relation(
        "contradicts",
        EnrichmentDimension.RESEARCH_PAPER,
        benchmarked=False,
        subject_types=("ResearchWork", "Document"),
    ),
    _relation(
        "extends",
        EnrichmentDimension.RESEARCH_PAPER,
        benchmarked=False,
        subject_types=("ResearchWork", "Document"),
    ),
    # Incident bridging is frozen semantically. It is benchmarked only after the bridge lands.
    _relation(
        "incident-exploits-vulnerability",
        EnrichmentDimension.INCIDENT_CONTEXT,
        benchmarked=False,
        target_types=("Vulnerability",),
    ),
    _relation(
        "incident-affects-object",
        EnrichmentDimension.INCIDENT_CONTEXT,
        benchmarked=False,
    ),
)

# Provider/source fields are retained for provenance and current projections. They become
# competition facts only after an explicit canonical mapping.
SOURCE_SPECIFIC_CLAIMS = frozenset(
    {
        "status",
        "title",
        "description_en",
        "assigner",
        "affected_products",
        "references",
        "published",
        "last_modified",
        "cwes",
    }
)
SOURCE_SPECIFIC_PREFIXES = (
    "github_",
    "osv_",
    "kev_",
    "cnvd_",
    "cnnvd_",
)

CANONICAL_OBJECT_TYPES = frozenset(
    {
        "Vulnerability",
        "Product",
        "Package",
        "SoftwareVersion",
        "InternetAsset",
        "Repo",
        "Issue",
        "PullRequest",
        "Commit",
        "Release",
        "ResearchWork",
        "Document",
        "Weakness",
        "ExploitArtifact",
    }
)

_CANONICAL_INDEX = {(item.kind, item.name): item for item in CANONICAL_TERMS}


def canonical_term(kind: Literal["claim", "relation"], name: str) -> VocabularyTerm | None:
    return _CANONICAL_INDEX.get((kind, name))


def classify_term(
    kind: Literal["claim", "relation"],
    name: str,
    *,
    origin: KnowledgeOrigin,
    subject_type: str | None = None,
    target_type: str | None = None,
    qualifier_keys: Collection[str] | None = None,
) -> VocabularyScope:
    term = canonical_term(kind, name)
    if term is not None:
        shape_matches = (
            not term.subject_types or subject_type is None or subject_type in term.subject_types
        ) and (not term.target_types or target_type is None or target_type in term.target_types)
        qualifier_matches = (
            qualifier_keys is None
            or not term.required_qualifier_keys
            or set(term.required_qualifier_keys) <= set(qualifier_keys)
        )
        if shape_matches and qualifier_matches:
            return VocabularyScope.CANONICAL
        if origin == "semantic_derived":
            return VocabularyScope.EXPLORATORY
        return VocabularyScope.UNREGISTERED
    if kind == "claim" and (
        name in SOURCE_SPECIFIC_CLAIMS or name.startswith(SOURCE_SPECIFIC_PREFIXES)
    ):
        return VocabularyScope.SOURCE_SPECIFIC
    if origin == "semantic_derived":
        return VocabularyScope.EXPLORATORY
    return VocabularyScope.UNREGISTERED


def classify_object_type(object_type: str, *, origin: KnowledgeOrigin) -> VocabularyScope:
    if object_type in CANONICAL_OBJECT_TYPES:
        return VocabularyScope.CANONICAL
    if origin == "semantic_derived":
        return VocabularyScope.EXPLORATORY
    return VocabularyScope.UNREGISTERED


def vocabulary_metadata(scope: VocabularyScope) -> dict[str, str]:
    return {
        "vocabulary_revision": VOCABULARY_REVISION,
        "vocabulary_scope": scope.value,
    }
