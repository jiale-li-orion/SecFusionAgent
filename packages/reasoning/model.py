from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field, JsonValue

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import EvidenceNeedContract, InvestigationState
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionConclusion, DecisionDraft, DecisionReportParagraph
from packages.shared.model_provider import ModelProvider, StructuredModelRequest


class DecisionModelActionKind(StrEnum):
    FINAL = "final"
    CONTINUE = "continue"


class FinalDecisionProposal(BaseModel):
    kind: Literal[DecisionModelActionKind.FINAL] = DecisionModelActionKind.FINAL
    conclusions: list[DecisionConclusion] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    answer_payload: dict[str, JsonValue] = Field(default_factory=dict)
    report_paragraphs: list[DecisionReportParagraph] = Field(default_factory=list)
    stop_reason: str = Field(min_length=1, max_length=128)


class ContinuationProposal(BaseModel):
    kind: Literal[DecisionModelActionKind.CONTINUE] = DecisionModelActionKind.CONTINUE
    proposition_or_question: str
    purpose: str = Field(min_length=1, max_length=128)
    target_objects: list[str] = Field(default_factory=list)
    evidence_contract: EvidenceNeedContract = Field(default_factory=EvidenceNeedContract)
    preferred_source_roles: list[str] = Field(default_factory=list)
    freshness_requirement: dict[str, JsonValue] = Field(default_factory=dict)
    priority: int = Field(default=50, ge=0, le=100)
    reason: str = Field(min_length=1)


DecisionModelAction = Annotated[
    FinalDecisionProposal | ContinuationProposal,
    Field(discriminator="kind"),
]


class DecisionPlannerResponse(BaseModel):
    action: DecisionModelAction


REPORT_INSTRUCTION = (
    "After deciding the structured answer_payload and conclusions, write "
    "report_paragraphs as a concise research report for a security analyst in "
    "the language of the user's question. Write two to four coherent prose "
    "paragraphs, each with complete subject-predicate sentences. Start with "
    "the direct answer and scope; explain why the cited source material "
    "supports the answer; then describe material uncertainty or a next step "
    "only when justified. Interpret the facts for a reader instead of listing "
    "fields, copying raw propositions, counting citations, or describing the "
    "system's internal validation. The prose must not mention "
    "InvestigationState, state items, propositions, answer_payload, conclusion "
    "objects, EvidenceRefs, session history, or the number of supporting rows. "
    "Do not claim source agreement or independent corroboration merely from "
    "citation counts. Name a publisher or document only if supported by the "
    "supplied conclusions or citation_sources. Derive every factual claim from "
    "the structured answer, conclusions, conflicts, unknowns, and identified "
    "citation sources; distinguish confirmed facts from inference and open "
    "questions. Do not invent claims, dates, versions, or sources. For each "
    "paragraph, include only evidence_refs already used by its supporting "
    "conclusions; use an empty list for a paragraph containing only an "
    "uncited uncertainty or recommendation. The report is presentation text; "
    "answer_payload and conclusions remain the decision authority. "
)


class ModelDecisionPlanner:
    PROMPT_REVISION = "decision-model-v2"
    REPORT_PROMPT_REVISION = "decision-model-v4"

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    async def plan(
        self,
        state: InvestigationState,
        *,
        citation_sources: list[CitationSource],
        session_context: list[dict[str, JsonValue]] | None = None,
        runtime_metadata: dict[str, JsonValue] | None = None,
        include_report: bool = False,
    ) -> DecisionDraft | ContinuationRequest:
        prompt_revision = (
            self.REPORT_PROMPT_REVISION if include_report else self.PROMPT_REVISION
        )
        metadata: dict[str, JsonValue] = {
            "model_purpose": "m6.decision",
            "prompt_revision": prompt_revision,
            "request_owner_ref": f"case:{state.case_id}",
            "planner": prompt_revision,
            "model_provider": f"{self._provider.name}@{self._provider.version}",
            "case_id": state.case_id,
            "case_revision": state.case_revision,
        }
        if runtime_metadata:
            metadata.update(runtime_metadata)
        request = StructuredModelRequest(
            system_instruction=(
                "You are the M6 Decision Runtime. Read only the supplied M4 InvestigationState. "
                "Do not invent tools, EvidenceNeed IDs, Case revisions, or evidence. "
                "Facts may cite only evidence_refs already present in confirmed state. "
                "For a fact conclusion, copy the statement exactly from one confirmed "
                "InvestigationState proposition and cite evidence_refs from that same item. "
                "Return the minimal sufficient answer to the user's question. Do not add related "
                "facts the user did not ask for, and do not restate an already-supported fact as "
                "a second inference merely to explain it. answer_payload should contain only the "
                "fields needed for the requested answer. "
                f"{REPORT_INSTRUCTION if include_report else ''}"
                "If you request continuation for a targetless retrieval question, select the "
                "relevant durable target_objects only from InvestigationState.targets; do not "
                "use chunk IDs, URLs, or invented object IDs as targets. "
                "session_context, when present, is conversation history for resolving references "
                "and user intent only. It is not evidence or current truth. Do not cite it, and "
                "do not treat a prior answer as a fact unless the same proposition is supported "
                "by the current InvestigationState. "
                "Inferences must preserve "
                "their support. If the current state cannot support a defensible answer, return a "
                "continuation proposal describing the evidence gap instead of guessing. "
                "For a final answer, stop_reason is a short machine-readable lifecycle code, "
                "prefer snake_case such as evidence_sufficient; do not put explanation text there. "
                "For continuation, purpose is likewise a short machine-readable purpose code, "
                "prefer snake_case such as verify_cvss_score; put the explanation in reason."
            ),
            data={
                "investigation_state": cast(JsonValue, state.model_dump(mode="json")),
                "citation_sources": cast(
                    JsonValue,
                    [item.model_dump(mode="json") for item in citation_sources],
                ),
                "session_context": cast(JsonValue, list(session_context or [])),
            },
            metadata=metadata,
        )
        response = await self._provider.generate_structured(request, DecisionPlannerResponse)
        action = response.action
        if isinstance(action, FinalDecisionProposal):
            return DecisionDraft(
                case_id=state.case_id,
                case_revision=state.case_revision,
                conclusions=action.conclusions,
                conflicts=action.conflicts,
                unknowns=action.unknowns,
                assumptions=action.assumptions,
                answer_payload=action.answer_payload,
                report_paragraphs=action.report_paragraphs if include_report else [],
                stop_reason=action.stop_reason,
                model_prompt_revision=prompt_revision,
            )
        return ContinuationRequest(
            request_id=_continuation_request_id(state, action),
            case_id=state.case_id,
            base_case_revision=state.case_revision,
            proposition_or_question=action.proposition_or_question,
            purpose=action.purpose,
            target_objects=action.target_objects,
            evidence_contract=action.evidence_contract,
            preferred_source_roles=action.preferred_source_roles,
            freshness_requirement=action.freshness_requirement,
            priority=action.priority,
            reason=action.reason,
        )


def _continuation_request_id(
    state: InvestigationState,
    proposal: ContinuationProposal,
) -> str:
    payload = {
        "case_id": state.case_id,
        "case_revision": state.case_revision,
        "proposal": proposal.model_dump(mode="json"),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return f"continuation:{digest[:32]}"
