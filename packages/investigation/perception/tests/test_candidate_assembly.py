from packages.intelligence.retrieval.contracts import CandidateKind, RetrievedCandidate
from packages.investigation.perception.assembly import CandidateAssembler
from packages.investigation.perception.contracts import EvidenceRequirement


def _candidate(
    candidate_id: str,
    *,
    source_id: str,
    source_role: str,
    source_family: str,
    upstream_source: str | None = None,
    scores: dict[str, float] | None = None,
) -> RetrievedCandidate:
    return RetrievedCandidate(
        candidate_id=candidate_id,
        candidate_kind=CandidateKind.DOCUMENT_CHUNK,
        document_chunk_id=candidate_id,
        source_id=source_id,
        source_role=source_role,
        source_family=source_family,
        upstream_source=upstream_source,
        score_channels=scores or {},
    )


def test_assembler_merges_score_channels_without_fusing_authority() -> None:
    candidates = [
        _candidate(
            "chunk-1",
            source_id="vendor-a",
            source_role="primary",
            source_family="vendor-a",
            scores={"lexical": 0.7},
        ),
        _candidate(
            "chunk-1",
            source_id="vendor-a",
            source_role="primary",
            source_family="vendor-a",
            scores={"dense": 0.9},
        ),
    ]

    result = CandidateAssembler().assemble(
        candidates,
        EvidenceRequirement(required_source_roles=["primary"], min_independent_sources=1),
    )

    assert result.requirements_satisfied is True
    assert len(result.candidates) == 1
    assert result.candidates[0].score_channels == {"lexical": 0.7, "dense": 0.9}
    assert result.independent_source_keys == ["family:vendor-a"]


def test_assembler_collapses_republication_and_reports_missing_authority() -> None:
    candidates = [
        _candidate(
            "chunk-a",
            source_id="media-a",
            source_role="signal",
            source_family="media-a",
            upstream_source="vendor-origin",
        ),
        _candidate(
            "chunk-b",
            source_id="media-b",
            source_role="signal",
            source_family="media-b",
            upstream_source="vendor-origin",
        ),
    ]

    result = CandidateAssembler().assemble(
        candidates,
        EvidenceRequirement(required_source_roles=["authority"], min_independent_sources=2),
    )

    assert result.requirements_satisfied is False
    assert result.independent_source_keys == ["upstream:vendor-origin"]
    assert "required_source_role_missing:authority" in result.unresolved
    assert "independent_source_requirement_unsatisfied:1/2" in result.unresolved
