from __future__ import annotations

from packages.intelligence.retrieval.contracts import RetrievedCandidate
from packages.investigation.perception.contracts import (
    CandidateAssemblyResult,
    EvidenceRequirement,
)


class CandidateAssembler:
    ASSEMBLER_REVISION = "candidate-assembler-v1"

    def assemble(
        self,
        candidates: list[RetrievedCandidate],
        requirement: EvidenceRequirement,
    ) -> CandidateAssemblyResult:
        merged: dict[str, RetrievedCandidate] = {}
        for candidate in candidates:
            current = merged.get(candidate.candidate_id)
            if current is None:
                merged[candidate.candidate_id] = candidate.model_copy(deep=True)
                continue
            scores = dict(current.score_channels)
            for channel, value in candidate.score_channels.items():
                scores[channel] = max(scores.get(channel, float("-inf")), value)
            current.score_channels = scores

        ordered = sorted(merged.values(), key=_candidate_sort_key)
        limited = ordered[: requirement.max_candidates]
        source_roles = sorted({item.source_role for item in limited if item.source_role})
        independent_keys: set[str] = set()
        for item in limited:
            key = _independence_key(item)
            if key is not None:
                independent_keys.add(key)
        independent = sorted(independent_keys)

        unresolved: list[str] = []
        for role in requirement.required_source_roles:
            if role not in source_roles:
                unresolved.append(f"required_source_role_missing:{role}")
        if len(independent) < requirement.min_independent_sources:
            unresolved.append(
                "independent_source_requirement_unsatisfied:"
                f"{len(independent)}/{requirement.min_independent_sources}"
            )
        if not limited:
            unresolved.append("no_candidates")

        return CandidateAssemblyResult(
            candidates=limited,
            independent_source_keys=independent,
            source_roles=source_roles,
            requirements_satisfied=not unresolved,
            unresolved=unresolved,
        )


def _independence_key(candidate: RetrievedCandidate) -> str | None:
    if candidate.upstream_source:
        return f"upstream:{candidate.upstream_source}"
    if candidate.source_family:
        return f"family:{candidate.source_family}"
    if candidate.source_id:
        return f"source:{candidate.source_id}"
    return None


def _candidate_sort_key(candidate: RetrievedCandidate) -> tuple[float | str, ...]:
    channels = candidate.score_channels
    # This is presentation ordering only. It deliberately does not convert
    # source authority into a retrieval score or a single fused confidence.
    return (
        -channels.get("exact", 0.0),
        -channels.get("structured", 0.0),
        -channels.get("evidence", 0.0),
        -channels.get("graph", 0.0),
        -channels.get("lexical", 0.0),
        -channels.get("dense", 0.0),
        -channels.get("freshness", 0.0),
        candidate.candidate_id,
    )
