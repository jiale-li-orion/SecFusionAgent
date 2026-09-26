import pytest

from packages.intelligence.knowledge.contracts import (
    ClaimCandidate,
    EnrichmentCandidate,
    ObjectCandidate,
    RelationCandidate,
)
from packages.intelligence.knowledge.write import (
    _validate_candidate_shapes,
    _validate_candidate_vocabulary,
)


def test_deterministic_writer_rejects_unregistered_terms() -> None:
    candidate = EnrichmentCandidate(
        root_object=ObjectCandidate(
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-0001",
        ),
        claims=[
            ClaimCandidate(
                predicate="invented_deterministic_fact",
                value=True,
                locator={"kind": "fixture", "path": "$.invented"},
            )
        ],
    )
    with pytest.raises(ValueError, match="unregistered canonical claim predicate"):
        _validate_candidate_vocabulary(candidate, origin="deterministic_derived")


def test_semantic_writer_allows_exploratory_terms_without_promoting_them_to_canonical() -> None:
    candidate = EnrichmentCandidate(
        root_object=ObjectCandidate(
            object_type="ResearchWork",
            canonical_key="paper:example",
        ),
        claims=[
            ClaimCandidate(
                predicate="novel_semantic_observation",
                value="supported by quoted evidence",
                locator={"kind": "fixture", "path": "$.text"},
            )
        ],
    )
    _validate_candidate_vocabulary(candidate, origin="semantic_derived")


def test_deterministic_canonical_relation_enforces_registered_shape() -> None:
    candidate = EnrichmentCandidate(
        root_object=ObjectCandidate(
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-0001",
        ),
        relations=[
            RelationCandidate(
                relation_type="affects-package",
                target=ObjectCandidate(
                    object_type="ResearchWork",
                    canonical_key="paper:not-a-package",
                ),
                locator={"kind": "fixture", "path": "$.text"},
            )
        ],
    )
    _validate_candidate_vocabulary(candidate, origin="deterministic_derived")
    with pytest.raises(ValueError, match="canonical relation shape mismatch"):
        _validate_candidate_shapes(
            candidate, origin="deterministic_derived", subject_type="Vulnerability"
        )
