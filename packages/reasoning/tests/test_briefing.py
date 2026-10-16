from datetime import UTC, datetime

import pytest

from packages.investigation.briefing import BriefingMaterial, BriefingPacket, BriefingPassage
from packages.reasoning.briefing import BriefingGenerator

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def packet():
    return BriefingPacket(
        topic="Agent 运行时安全",
        materials=[
            BriefingMaterial(
                document_id="doc-1",
                revision_id="rev-1",
                source_id="vendor",
                source_role="primary",
                origin_key="vendor",
                title="Testing agent boundaries",
                url="https://example.org/safety",
                published_at=NOW,
                passages=[
                    BriefingPassage(
                        evidence_ref="document-chunk:c1@rev-1",
                        text="The vendor reports 12 tests in a simulated environment.",
                    )
                ],
            )
        ],
    )


class Provider:
    name = "fixture"
    version = "1"

    def __init__(self, *, supported=True, complete=True):
        self.supported, self.complete = supported, complete
        self.requests = []

    async def generate_structured(self, request, response_model):
        self.requests.append(request)
        if "action" in response_model.model_fields:
            return response_model.model_validate(
                {
                    "action": {
                        "kind": "final",
                        "conclusions": [
                            {
                                "type": "inference",
                                "statement": "厂商称在模拟环境完成了 12 项测试。",
                                "evidence_refs": ["document-chunk:c1@rev-1"],
                            }
                        ],
                        "report_summary": {
                            "text": "厂商在模拟环境进行了 12 项 Agent 测试。",
                            "evidence_refs": ["document-chunk:c1@rev-1"],
                        },
                        "report_paragraphs": [
                            {
                                "text": "厂商称在模拟环境完成了 12 项测试。",
                                "evidence_refs": ["document-chunk:c1@rev-1"],
                            }
                        ],
                        "report_layout": {"title": "Agent 边界测试的适用范围"},
                        "unknowns": ["真实部署效果没有独立验证。"],
                        "stop_reason": "partial_evidence",
                    }
                }
            )
        return response_model.model_validate(
            {
                "summary_supported": True,
                "title_supported": True,
                "scope_honest": True,
                "attribution_correct": True,
                "editorial_quality": True,
                "paragraphs": [
                    {
                        "paragraph_index": 0,
                        "supported": self.supported,
                        "reason": "Source describes simulated tests.",
                    }
                ]
                if self.complete
                else [],
                "issues": [] if self.supported else ["Unsupported number."],
            }
        )


async def test_public_brief_uses_tentative_sources_and_requires_review():
    provider = Provider()
    result = await BriefingGenerator(provider).generate(packet(), now=NOW)
    assert result.publishable
    assert len(provider.requests) == 2
    assert (
        "Return a final report with only the confirmed facts"
        not in provider.requests[0].system_instruction
    )
    assert "clearly attributed source assertions" in provider.requests[0].system_instruction
    state = provider.requests[0].data["investigation_state"]
    assert not state["confirmed"]
    assert state["tentative"]
    assert "primary" in state["tentative"][0]["proposition"]
    assert result.decision.report_layout is not None
    assert result.decision.report_layout.title == "Agent 边界测试的适用范围"


@pytest.mark.parametrize("supported,complete", [(False, True), (True, False)])
async def test_public_brief_requires_complete_supported_review(supported, complete):
    result = await BriefingGenerator(Provider(supported=supported, complete=complete)).generate(
        packet(),
        now=NOW,
    )
    assert not result.publishable


def test_daily_brief_rejects_unknown_or_outside_publication_window():
    material = packet().materials[0].model_copy(update={"published_at": None})
    with pytest.raises(ValueError, match="publication time"):
        BriefingPacket(
            topic="Daily", materials=[material], window_start=NOW, window_end=NOW.replace(hour=23)
        )


def test_same_upstream_is_not_counted_as_independent():
    original = packet().materials[0]
    copy = original.model_copy(update={"document_id": "doc-2", "source_id": "reprint"})
    assert BriefingPacket(topic="Safety", materials=[original, copy]).origin_count == 1


@pytest.mark.parametrize(
    "problem", ["internal_state", "conclusion_state", "long_paragraph", "editorial_review"]
)
async def test_supported_report_cannot_publish_with_editorial_defects(problem):
    class DefectiveProvider(Provider):
        async def generate_structured(self, request, response_model):
            result = await super().generate_structured(request, response_model)
            if "action" in response_model.model_fields:
                if problem == "internal_state":
                    result.action.unknowns = ["当前调查状态中没有已确认命题。"]
                elif problem == "conclusion_state":
                    result.action.conclusions[0].statement = "当前调查状态中没有已确认命题。"
                elif problem == "long_paragraph":
                    result.action.report_paragraphs[0].text = "厂商称已在模拟环境完成测试。" * 60
            elif problem == "editorial_review":
                result.editorial_quality = False
            return result

    result = await BriefingGenerator(DefectiveProvider()).generate(packet(), now=NOW)
    assert not result.publishable
    if problem != "editorial_review":
        assert result.publication_issues


@pytest.mark.parametrize(
    "problem", ["absent", "uncited", "unsupported", "self_description", "long"]
)
async def test_public_summary_is_mandatory_cited_and_independently_reviewed(problem):
    class SummaryProvider(Provider):
        async def generate_structured(self, request, response_model):
            result = await super().generate_structured(request, response_model)
            if "action" in response_model.model_fields:
                if problem == "absent":
                    result.action.report_summary = None
                elif problem == "uncited":
                    result.action.report_summary.evidence_refs = []
                elif problem == "self_description":
                    result.action.report_summary.text = "本报告旨在向读者梳理重要信息。"
                elif problem == "long":
                    result.action.report_summary.text = "测试" * 201
            elif problem == "unsupported":
                result.summary_supported = False
            return result

    result = await BriefingGenerator(SummaryProvider()).generate(packet(), now=NOW)
    assert not result.publishable


async def test_summary_appears_in_critic_input_and_has_separate_citations():
    provider = Provider()
    result = await BriefingGenerator(provider).generate(packet(), now=NOW)
    assert result.decision.report_summary is not None
    assert result.decision.report_summary.text != result.decision.report_paragraphs[0].text
    assert provider.requests[1].data["report"]["report_summary"]["evidence_refs"]


async def test_public_prompt_does_not_inherit_defensive_research_opening():
    provider = Provider()
    await BriefingGenerator(provider).generate(packet(), now=NOW)
    instruction = provider.requests[0].system_instruction
    assert "State material coverage gaps in the opening paragraph" not in instruction
    assert "不写“本报告/本文旨在" in instruction
    assert "同时存在于支撑它的 conclusions" in instruction


async def test_one_editorial_revision_is_rechecked_and_bounded():
    class RepairProvider(Provider):
        async def generate_structured(self, request, response_model):
            result = await super().generate_structured(request, response_model)
            if request.metadata["model_purpose"] == "m6.editorial_review":
                if len(self.requests) == 2:
                    result.summary_supported = False
                    result.issues = ["Summary needs attribution."]
            return result

    provider = RepairProvider()
    result = await BriefingGenerator(provider).generate(packet(), now=NOW)
    assert result.publishable
    assert [r.metadata["model_purpose"] for r in provider.requests] == [
        "m6.public_briefing",
        "m6.editorial_review",
        "m6.editorial_revision",
        "m6.editorial_review",
    ]
    assert provider.requests[2].data["review"]["issues"]
    rejected = Provider(supported=False)
    assert not (await BriefingGenerator(rejected).generate(packet(), now=NOW)).publishable
    assert len(rejected.requests) == 4
