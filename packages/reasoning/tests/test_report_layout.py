import pytest

from packages.reasoning.decision import DecisionDraft, DecisionService
from packages.reasoning.tests.test_decision import _state


def draft(layout):
    return DecisionDraft.model_validate(
        {
            "case_id": "case-1",
            "case_revision": 4,
            "report_paragraphs": [{"text": "尚未确认影响范围。"}, {"text": "需要进一步验证。"}],
            "report_layout": layout,
            "stop_reason": "partial_evidence",
            "model_prompt_revision": "report-test",
        }
    )


def test_report_layout_survives_validated_decision():
    result = DecisionService().decide(
        _state(),
        draft(
            {
                "title": "影响范围仍待验证",
                "sections": [
                    {"heading": "已知边界", "paragraph_indices": [0]},
                    {"heading": "后续核查", "paragraph_indices": [1]},
                ],
            }
        ),
        citation_sources=[],
    )
    assert result.model_dump()["report_layout"]["title"] == "影响范围仍待验证"


@pytest.mark.parametrize("indices", [[0], [0, 0], [0, 2]])
def test_report_layout_cannot_hide_duplicate_or_invent_paragraphs(indices):
    with pytest.raises(ValueError, match="every report paragraph exactly once"):
        DecisionService().decide(
            _state(),
            draft(
                {
                    "title": "核查报告",
                    "sections": [{"heading": "发现", "paragraph_indices": indices}],
                }
            ),
            citation_sources=[],
        )
