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
from packages.reasoning.editorial_prompt import (
    PUBLIC_BRIEFING_INSTRUCTION,
    PUBLIC_BRIEFING_PROMPT_REVISION,
)
from packages.reasoning.report_layout import ReportLayout
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
    report_summary: DecisionReportParagraph | None = None
    report_paragraphs: list[DecisionReportParagraph] = Field(default_factory=list)
    report_layout: ReportLayout | None = None
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


class InvestigationReportResponse(DecisionPlannerResponse):
    """A finished investigation episode must deliver a report, including its gaps."""

    action: FinalDecisionProposal


ANSWER_INSTRUCTION = (
    "Return the minimal sufficient answer to the user's question. Choose scope from the "
    "question, not from how much evidence is available. "
    "Source-record lookup: For a question about recorded fields, status or relationships, "
    "answer within the named source and time scope. Select only the requested confirmed "
    "facts and required intermediate path relations. A recorded negative status is a complete "
    "answer. Apply sorting and tie-breaking internally; selection is not another conclusion. "
    "When the requested facts are present and unconflicted, return evidence_sufficient with "
    "empty unknowns, conflicts and assumptions. Do not turn unrequested independent checks, "
    "later events or unrelated fields into gaps. Record missing requested facts or conflicting "
    "evidence as gaps; a bounded record does not establish a broader real-world claim. "
    "Analytical investigation: For requested explanation, risk, verification or broader context, "
    "address every requested dimension. Use inference for supported judgments or clearly "
    "attributed source assertions, preserving premises, evidence and uncertainty. Missing "
    "requested dimensions remain unknown; metadata alone does not establish security, "
    "maintenance or safety. Empty state lists do not prove absence. "
    "For a fact, copy one confirmed proposition exactly, including any semantics= suffix, "
    "qualifiers and identifiers, with evidence_refs from that same state item. Same-source "
    "evidence is not interchangeable. Do not restate a fact as an inference. answer_payload "
    "contains only the requested answer. report_summary and report_paragraphs may cite only "
    "refs used by conclusions that support their text. Do not add conclusions to authorize "
    "extra report citations; remove the extra prose instead. "
)


REPORT_INSTRUCTION = (
    "Write report_paragraphs in the user's language after selecting the structured answer. "
    "For a source-record lookup, give the direct answer in a short paragraph, or one per "
    "requested relationship. Omit selection commentary and generic caveats. Leave optional "
    "report_summary and report_layout null when they would only repeat the answer. "
    "For an analytical investigation, write a concise research report for a security analyst: "
    "usually one to four coherent paragraphs, up to 24 for a multi-event briefing. Explain "
    "supported findings and their implications; state material requested gaps clearly and "
    "early. Add a next step only when it helps resolve those gaps. Preserve attribution, "
    "experimental conditions and dates; publication, event and collection times differ. "
    "Do not infer independent corroboration from citation counts or repeated upstream reports. "
    "Use complete sentences and only claims supported by the selected answer. Name sources "
    "only from supplied citation metadata or conclusions. Paragraphs and summaries containing "
    "only uncertainty or recommendations can have empty evidence_refs. Titles and headings "
    "follow the same support and scope rules. Optional report_layout sections must cover every "
    "zero-based paragraph index exactly once. Use editorial style for a focused investigation "
    "and briefing for multiple events. Do not mention InvestigationState, state items, "
    "propositions, answer_payload, conclusion objects, EvidenceRefs or internal validation. "
    "Do not emit HTML, CSS, scripts, assets or Markdown tables. Reports are presentation; "
    "structured conclusions and answer_payload remain authoritative. "
)

class ModelDecisionPlanner:
    PROMPT_REVISION = "decision-model-v9-core"
    REPORT_PROMPT_REVISION = "decision-model-v9"
    METHODOLOGY_PROMPT_REVISION = "decision-methodology-v3"

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
        prefer_partial_final: bool = False,
        methodology_mode: bool = False,
        public_briefing: bool = False,
    ) -> DecisionDraft | ContinuationRequest:
        prompt_revision = (
            PUBLIC_BRIEFING_PROMPT_REVISION
            if public_briefing and include_report
            else self.METHODOLOGY_PROMPT_REVISION
            if methodology_mode
            else self.REPORT_PROMPT_REVISION
            if include_report
            else self.PROMPT_REVISION
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
        lifecycle_instruction = (
            ""
            if methodology_mode
            else (
                "The current investigation episode has ended. Return a final report with supported "
                "facts, clearly attributed source assertions and inferences. Keep requested gaps "
                "in unknowns and use partial_evidence when they remain; "
                "do not request continuation. "
                if prefer_partial_final
                else "If evidence cannot support the requested answer, request continuation for "
                "that gap instead of guessing. Choose target_objects only from "
                "InvestigationState.targets; "
                "never invent object IDs or use URLs or chunk IDs as targets. "
            )
        )
        request = StructuredModelRequest(
            system_instruction=(
                "You are the M6 Decision Runtime. Read only the supplied M4 InvestigationState. "
                "Do not invent tools, EvidenceNeed IDs, Case revisions, or evidence. "
                "Facts may cite only evidence_refs already present in confirmed state. "
                f"{ANSWER_INSTRUCTION}"
                f"{REPORT_INSTRUCTION if include_report and not public_briefing else ''}"
                f"{PUBLIC_BRIEFING_INSTRUCTION if public_briefing and include_report else ''}"
                "session_context resolves references and user intent only. "
                "It is not evidence or current truth. Do not cite prior answers; "
                "facts must be supported by the current state. "
                f"{lifecycle_instruction}"
                "Use short machine-readable snake_case codes for stop_reason and continuation "
                "purpose, such as evidence_sufficient or verify_applicability; put explanations "
                "in report prose or continuation reason. "
                + (
                    "This is a targetless request for a general verification method, not a "
                    "claim about any particular vulnerability or project. Return a final "
                    "practical answer without requesting a target or continuation. Explain "
                    "what to check and why, in complete readable paragraphs. Use only "
                    "recommendation conclusions with empty evidence_refs; do not assert "
                    "that any specific version is fixed, or invent a source, result, or citation. "
                    "Set answer_payload to a compact methodology summary and stop_reason "
                    "to methodology_guidance."
                    if methodology_mode
                    else ""
                )
            ),
            data={
                "investigation_state": cast(JsonValue, state.model_dump(mode="json")),
                "citation_sources": cast(
                    JsonValue,
                    [item.model_dump(mode="json") for item in citation_sources],
                ),
                "session_context": cast(JsonValue, list(session_context or [])),
                "prefer_partial_final": prefer_partial_final,
                "methodology_mode": methodology_mode,
            },
            metadata=metadata,
        )
        response_model = (
            InvestigationReportResponse
            if prefer_partial_final or methodology_mode
            else DecisionPlannerResponse
        )
        response = await self._provider.generate_structured(request, response_model)
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
                report_layout=action.report_layout if include_report else None,
                report_summary=action.report_summary if include_report else None,
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
