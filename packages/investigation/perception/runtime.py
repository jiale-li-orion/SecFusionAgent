from __future__ import annotations

from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.contracts import RetrievedCandidate
from packages.intelligence.retrieval.operators import (
    DenseRetrievalOperator,
    DocumentRetrievalOperator,
    EvidenceRetrievalOperator,
    ExactRetrievalOperator,
    GraphRetrievalOperator,
    LexicalRetrievalOperator,
    StructuredRetrievalOperator,
)
from packages.investigation.perception.assembly import CandidateAssembler
from packages.investigation.perception.contracts import (
    Percept,
    PerceptionRequest,
    PerceptionStepResult,
    PhysicalObservationPort,
    PhysicalOperator,
    PhysicalPerceptionPlan,
)


class PerceptionRuntime:
    def __init__(self, physical_observation_port: PhysicalObservationPort | None = None) -> None:
        self._exact = ExactRetrievalOperator()
        self._structured = StructuredRetrievalOperator()
        self._lexical = LexicalRetrievalOperator()
        self._dense = DenseRetrievalOperator()
        self._document = DocumentRetrievalOperator()
        self._graph = GraphRetrievalOperator()
        self._evidence = EvidenceRetrievalOperator()
        self._assembler = CandidateAssembler()
        self._physical_observation_port = physical_observation_port

    async def execute(
        self,
        session: AsyncSession,
        *,
        request: PerceptionRequest,
        plan: PhysicalPerceptionPlan,
        task_run_id: str | None = None,
    ) -> Percept:
        if request.request_id != plan.request_id:
            raise ValueError("perception request and plan request_id differ")
        step_outputs: dict[str, PerceptionStepResult] = {}
        operator_counts: Counter[str] = Counter()
        warnings: list[str] = []
        observed_propositions = []
        observation_handles: list[str] = []
        external_cost: dict[str, object] = {}

        for step in plan.steps:
            output = await self._execute_step(
                session,
                request=request,
                step=step,
                step_outputs=step_outputs,
                task_run_id=task_run_id,
            )
            step_outputs[step.step_id] = output
            operator_counts[step.operator.value] += 1
            observed_propositions.extend(output.observed_propositions)
            observation_handles.extend(output.observation_handles)
            warnings.extend(output.unresolved)
            for key, value in output.cost.items():
                external_cost[f"{step.step_id}:{key}"] = value
            if step.operator is PhysicalOperator.DENSE and not output.candidates:
                warnings.append("dense_no_candidates_or_embeddings_unavailable")

        all_candidates = [
            candidate
            for step in plan.steps
            for candidate in step_outputs.get(step.step_id, PerceptionStepResult()).candidates
        ]
        assembled = self._assembler.assemble(
            all_candidates,
            request.evidence_requirement,
        )
        unresolved = list(dict.fromkeys([*assembled.unresolved, *warnings]))
        target_refs = sorted(
            {
                candidate.object_id
                for candidate in assembled.candidates
                if candidate.object_id is not None
            }
        )
        evidence_handles = sorted(
            {
                candidate.evidence_ref
                for candidate in assembled.candidates
                if candidate.evidence_ref is not None
            }
        )
        return Percept(
            percept_id=f"percept:{request.request_id}",
            request_id=request.request_id,
            target_refs=target_refs,
            observed_propositions=observed_propositions,
            candidate_evidence=assembled.candidates,
            evidence_handles=evidence_handles,
            observation_handles=sorted(set(observation_handles)),
            independent_source_keys=assembled.independent_source_keys,
            source_roles=assembled.source_roles,
            unresolved=unresolved,
            operator_counts=dict(operator_counts),
            cost={
                "operator_calls": sum(operator_counts.values()),
                **external_cost,
            },
            assembler_revision=self._assembler.ASSEMBLER_REVISION,
        )

    async def _execute_step(
        self,
        session: AsyncSession,
        *,
        request: PerceptionRequest,
        step,
        step_outputs: dict[str, PerceptionStepResult],
        task_run_id: str | None,
    ) -> PerceptionStepResult:
        payload = dict(step.input)
        dependency = step_outputs.get(step.dependency or "", PerceptionStepResult()).candidates
        if step.operator is PhysicalOperator.EXACT:
            return PerceptionStepResult(
                candidates=await self._exact.by_identifier(
                    session,
                    namespace=str(payload["namespace"]),
                    value=str(payload["value"]),
                )
            )
        if step.operator is PhysicalOperator.STRUCTURED:
            subject_ids = _subject_ids(payload, dependency)
            results: list[RetrievedCandidate] = []
            for subject_id in subject_ids:
                results.extend(
                    await self._structured.current(
                        session,
                        subject_id=subject_id,
                        projection_types=_string_list(payload.get("projection_types")),
                    )
                )
            return PerceptionStepResult(candidates=results)
        if step.operator is PhysicalOperator.DOCUMENT:
            results = []
            for subject_id in _subject_ids(payload, dependency):
                results.extend(
                    await self._document.for_object(
                        session, object_id=subject_id, limit=int(payload.get("limit", 20))
                    )
                )
            return PerceptionStepResult(candidates=results)
        if step.operator is PhysicalOperator.LEXICAL:
            return PerceptionStepResult(
                candidates=await self._lexical.search(
                    session,
                    query=str(payload["query"]),
                    limit=int(payload.get("limit", 20)),
                    source_ids=_string_list(payload.get("source_ids")),
                )
            )
        if step.operator is PhysicalOperator.DENSE:
            return PerceptionStepResult(
                candidates=await self._dense.search(
                    session,
                    query_vector=_float_list(payload.get("query_vector")),
                    limit=int(payload.get("limit", 20)),
                    source_ids=_string_list(payload.get("source_ids")),
                )
            )
        if step.operator is PhysicalOperator.GRAPH:
            object_ids = _subject_ids(payload, dependency)
            results = []
            for object_id in object_ids:
                results.extend(
                    await self._graph.neighbors(
                        session,
                        object_id=object_id,
                        direction=str(payload.get("direction", "out")),
                        relation_types=_string_list(payload.get("relation_types")),
                    )
                )
            return PerceptionStepResult(candidates=results)
        if step.operator is PhysicalOperator.EVIDENCE:
            return PerceptionStepResult(
                candidates=await self._evidence.for_target(
                    session,
                    target_kind=str(payload["target_kind"]),
                    target_id=str(payload["target_id"]),
                )
            )
        if step.operator in {PhysicalOperator.EXTERNAL, PhysicalOperator.SANDBOX}:
            if self._physical_observation_port is None:
                return PerceptionStepResult(
                    unresolved=[f"physical_operator_unavailable:{step.operator.value}"]
                )
            if task_run_id is None:
                raise ValueError(
                    f"{step.operator.value} perception requires task_run_id execution context"
                )
            return await self._physical_observation_port.execute(
                task_run_id=task_run_id,
                request=request,
                step=step,
            )
        raise ValueError(f"unsupported physical operator: {step.operator}")


def _subject_ids(
    payload: dict[str, object],
    dependency: list[RetrievedCandidate],
) -> list[str]:
    direct = payload.get("subject_id") or payload.get("object_id")
    if isinstance(direct, str) and direct:
        return [direct]
    return list(
        dict.fromkeys(
            candidate.object_id for candidate in dependency if candidate.object_id is not None
        )
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if isinstance(item, int | float)]
