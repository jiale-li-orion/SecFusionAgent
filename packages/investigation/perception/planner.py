from __future__ import annotations

from packages.investigation.perception.contracts import (
    PerceptionOperation,
    PerceptionRequest,
    PhysicalOperator,
    PhysicalPerceptionPlan,
    PhysicalPerceptionStep,
)


class PerceptionPlanner:
    PLANNER_REVISION = "perception-planner-v1"

    def plan(self, request: PerceptionRequest) -> PhysicalPerceptionPlan:
        target = request.target
        steps: list[PhysicalPerceptionStep] = []
        exact_step_id: str | None = None

        if target.identifier is not None:
            exact_step_id = "exact:0"
            steps.append(
                PhysicalPerceptionStep(
                    step_id=exact_step_id,
                    operator=PhysicalOperator.EXACT,
                    input={
                        "namespace": target.identifier.namespace,
                        "value": target.identifier.value,
                    },
                    expected_output_type="object",
                )
            )

        if request.operation is PerceptionOperation.INSPECT:
            if target.object_id is not None or exact_step_id is not None:
                structured_payload: dict[str, object] = {
                    "projection_types": target.projection_types
                }
                if target.object_id is not None:
                    structured_payload["subject_id"] = target.object_id
                steps.append(
                    PhysicalPerceptionStep(
                        step_id="structured:0",
                        operator=PhysicalOperator.STRUCTURED,
                        input=structured_payload,
                        dependency=None if target.object_id is not None else exact_step_id,
                        expected_output_type="projection",
                    )
                )

        if request.operation in {
            PerceptionOperation.EXPAND,
            PerceptionOperation.TRACE,
        }:
            graph_payload: dict[str, object] = {
                "direction": "both" if request.operation is PerceptionOperation.TRACE else "out",
                "relation_types": target.relation_types,
            }
            if target.object_id is not None:
                graph_payload["object_id"] = target.object_id
            if target.object_id is not None or exact_step_id is not None:
                steps.append(
                    PhysicalPerceptionStep(
                        step_id="graph:0",
                        operator=PhysicalOperator.GRAPH,
                        input=graph_payload,
                        dependency=None if target.object_id is not None else exact_step_id,
                        expected_output_type="relation",
                    )
                )

        if request.operation in {
            PerceptionOperation.SEARCH,
            PerceptionOperation.CORROBORATE,
            PerceptionOperation.CONTRAST,
        }:
            if target.query_text:
                steps.append(
                    PhysicalPerceptionStep(
                        step_id="lexical:0",
                        operator=PhysicalOperator.LEXICAL,
                        input={
                            "query": target.query_text,
                            "source_ids": target.source_ids,
                            "limit": request.evidence_requirement.max_candidates,
                        },
                        expected_output_type="document_chunk",
                    )
                )
            if target.query_vector:
                steps.append(
                    PhysicalPerceptionStep(
                        step_id="dense:0",
                        operator=PhysicalOperator.DENSE,
                        input={
                            "query_vector": target.query_vector,
                            "source_ids": target.source_ids,
                            "limit": request.evidence_requirement.max_candidates,
                        },
                        expected_output_type="document_chunk",
                    )
                )

        for index, evidence_target in enumerate(target.evidence_targets):
            steps.append(
                PhysicalPerceptionStep(
                    step_id=f"evidence:{index}",
                    operator=PhysicalOperator.EVIDENCE,
                    input={
                        "target_kind": evidence_target.target_kind,
                        "target_id": evidence_target.target_id,
                    },
                    expected_output_type="evidence",
                )
            )

        if request.operation is PerceptionOperation.OBSERVE_EXTERNAL:
            steps.append(
                PhysicalPerceptionStep(
                    step_id="external:0",
                    operator=PhysicalOperator.EXTERNAL,
                    input={
                        "identifier": (
                            target.identifier.model_dump(mode="json")
                            if target.identifier is not None
                            else None
                        ),
                        "object_id": target.object_id,
                        "query_text": target.query_text,
                        "source_ids": target.source_ids,
                        "desired_observation": request.desired_observation,
                        "time_scope": request.time_scope,
                    },
                    expected_output_type="ephemeral_observation",
                    capability_requirement="external_observation",
                    estimated_cost="medium",
                )
            )

        return PhysicalPerceptionPlan(
            request_id=request.request_id,
            steps=steps,
            planner_revision=self.PLANNER_REVISION,
        )
