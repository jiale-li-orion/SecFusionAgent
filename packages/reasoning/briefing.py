"""Evidence-bound editorial generation and a separate model critique pass."""

import re
from datetime import datetime
from typing import cast

from pydantic import BaseModel, Field, JsonValue

from packages.investigation.briefing import BriefingPacket, briefing_state
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionDraft, DecisionResult, DecisionService
from packages.reasoning.editorial_prompt import (
    EDITORIAL_REVIEW_INSTRUCTION,
    EDITORIAL_REVISION_INSTRUCTION,
    PUBLIC_BRIEFING_PROMPT_REVISION,
)
from packages.reasoning.model import InvestigationReportResponse, ModelDecisionPlanner
from packages.shared.model_provider import ModelProvider, StructuredModelRequest

BRIEFING_POLICY = "public-briefing-v2"
REVIEW_PROMPT = "editorial-review-v5"


class ParagraphReview(BaseModel):
    paragraph_index: int = Field(ge=0)
    supported: bool
    reason: str = Field(min_length=1, max_length=1000)


class BriefingReview(BaseModel):
    summary_supported: bool
    title_supported: bool
    scope_honest: bool
    attribution_correct: bool
    editorial_quality: bool
    paragraphs: list[ParagraphReview]
    issues: list[str] = Field(default_factory=list)

    def accepts(self, paragraph_count: int) -> bool:
        return (
            paragraph_count > 0
            and self.summary_supported
            and self.title_supported
            and self.scope_honest
            and self.attribution_correct
            and self.editorial_quality
            and not self.issues
            and sorted(item.paragraph_index for item in self.paragraphs)
            == list(range(paragraph_count))
            and all(item.supported for item in self.paragraphs)
        )


class GeneratedBriefing(BaseModel):
    decision: DecisionResult
    review: BriefingReview
    publication_issues: list[str] = Field(default_factory=list)
    revision_history: list[dict[str, JsonValue]] = Field(default_factory=list)

    @property
    def publishable(self) -> bool:
        return not self.publication_issues and self.review.accepts(
            len(self.decision.report_paragraphs)
        )


class BriefingGenerator:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    @property
    def policy(self) -> str:
        return (
            f"{BRIEFING_POLICY}:{PUBLIC_BRIEFING_PROMPT_REVISION}:"
            f"{REVIEW_PROMPT}:{self.provider.name}@{self.provider.version}"
        )

    async def generate(self, packet: BriefingPacket, *, now: datetime) -> GeneratedBriefing:
        identity = "brief:" + packet.digest(policy=self.policy)[:32]
        state = briefing_state(packet, identity=identity, now=now)
        sources = [
            CitationSource(
                evidence_ref=passage.evidence_ref,
                source_ref=material.url,
                locator={"section": passage.section, "document_revision_id": material.revision_id},
            )
            for material in packet.materials
            for passage in material.passages
        ]
        draft = await ModelDecisionPlanner(self.provider).plan(
            state,
            citation_sources=sources,
            include_report=True,
            public_briefing=True,
            prefer_partial_final=True,
            runtime_metadata={
                "case_id": None,
                "request_owner_ref": identity,
                "model_purpose": "m6.public_briefing",
                "model_wall_seconds": 300,
            },
        )
        if not isinstance(draft, DecisionDraft):
            raise ValueError("briefing must return a report or explicit uncertainty")
        decision = DecisionService().decide(state, draft, citation_sources=sources)
        generated = await self.review(packet, decision)
        if generated.publishable:
            return generated
        return await self.revise(packet, generated, now=now)

    async def revise(
        self, packet: BriefingPacket, previous: GeneratedBriefing, *, now: datetime
    ) -> GeneratedBriefing:
        """One correction and fresh full review; never recursively repair until accepted."""
        identity = "brief:" + packet.digest(policy=self.policy)[:32]
        state = briefing_state(packet, identity=identity, now=now)
        sources = [
            CitationSource(
                evidence_ref=p.evidence_ref,
                source_ref=m.url,
                locator={"section": p.section, "document_revision_id": m.revision_id},
            )
            for m in packet.materials
            for p in m.passages
        ]
        response = await self.provider.generate_structured(
            StructuredModelRequest(
                system_instruction=EDITORIAL_REVISION_INSTRUCTION,
                data={
                    "source_packet": cast(JsonValue, packet.model_dump(mode="json")),
                    "draft": cast(JsonValue, previous.decision.model_dump(mode="json")),
                    "review": cast(JsonValue, previous.review.model_dump(mode="json")),
                    "publication_issues": cast(JsonValue, previous.publication_issues),
                },
                metadata={
                    "model_purpose": "m6.editorial_revision",
                    "prompt_revision": self.policy,
                    "request_owner_ref": identity,
                    "model_wall_seconds": 240,
                },
            ),
            InvestigationReportResponse,
        )
        draft = DecisionDraft(
            case_id=identity,
            case_revision=state.case_revision,
            model_prompt_revision=PUBLIC_BRIEFING_PROMPT_REVISION,
            **response.action.model_dump(exclude={"kind"}),
        )
        decision = DecisionService().decide(state, draft, citation_sources=sources)
        revised = await self.review(packet, decision)
        revised.revision_history = [
            {
                "decision_id": previous.decision.decision_id,
                "review": cast(JsonValue, previous.review.model_dump(mode="json")),
                "publication_issues": cast(JsonValue, previous.publication_issues),
            }
        ]
        return revised

    async def review(self, packet: BriefingPacket, decision: DecisionResult) -> GeneratedBriefing:
        identity = "brief:" + packet.digest(policy=self.policy)[:32]
        review = await self.provider.generate_structured(
            StructuredModelRequest(
                system_instruction=EDITORIAL_REVIEW_INSTRUCTION,
                data={
                    "source_packet": cast(JsonValue, packet.model_dump(mode="json")),
                    "report": cast(JsonValue, decision.model_dump(mode="json")),
                },
                metadata={
                    "model_purpose": "m6.editorial_review",
                    "prompt_revision": REVIEW_PROMPT,
                    "request_owner_ref": identity,
                    "model_wall_seconds": 300,
                },
            ),
            BriefingReview,
        )
        return GeneratedBriefing(
            decision=decision, review=review, publication_issues=publication_issues(decision)
        )


def publication_issues(decision: DecisionResult) -> list[str]:
    """Mechanical editorial checks complement (not replace) semantic review."""
    issues = []
    if decision.report_layout is None:
        issues.append("missing_report_layout")
    if not 1 <= len(decision.report_paragraphs) <= 24:
        issues.append("paragraph_count_out_of_bounds")
    for index, paragraph in enumerate(decision.report_paragraphs):
        if not paragraph.text.strip() or len(paragraph.text) > 600:
            issues.append(f"paragraph_{index}_length_out_of_bounds")
    summary = decision.report_summary
    if summary is None or not summary.text.strip():
        issues.append("missing_report_summary")
    elif not summary.evidence_refs:
        issues.append("uncited_report_summary")
    elif len(summary.text) > 400:
        issues.append("summary_length_out_of_bounds")
    if summary and re.search(
        r"本报告旨在|本文旨在|本报告将|以下是.*摘要|供读者自行判断|基于所列公开材料", summary.text
    ):
        issues.append("summary_self_description")
    visible = [p.text for p in decision.report_paragraphs]
    if summary:
        visible.append(summary.text)
    visible.extend(item.statement for item in decision.conclusions)
    visible.extend(decision.unknowns + decision.conflicts + decision.assumptions)
    if decision.report_layout:
        visible.append(decision.report_layout.title)
        visible.extend(s.heading for s in decision.report_layout.sections)
    if re.search(
        r"InvestigationState|answer_payload|EvidenceRefs?|已确认命题|空冲突列表|"
        r"当前调查状态|当前状态无已确认事实|来源断言形式保存|confirmed\s+state",
        "\n".join(visible),
        re.IGNORECASE,
    ):
        issues.append("internal_state_vocabulary")
    return issues
