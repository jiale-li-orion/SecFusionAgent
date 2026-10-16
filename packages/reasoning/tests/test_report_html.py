from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from packages.reasoning.report_html import ReportDocument, render_report_html


def report(**overrides):
    return ReportDocument.model_validate(
        {
            "decision_id": "decision:test",
            "case_revision": 2,
            "created_at": datetime(2026, 10, 15, tzinfo=UTC),
            "conclusions": [
                {"type": "fact", "statement": "厂商报告了测试结果。", "evidence_refs": ["e1"]}
            ],
            "report_paragraphs": [
                {"text": "厂商称测试已完成。尚无独立复核。", "evidence_refs": ["e1"]}
            ],
            "citations": [
                {
                    "conclusion_index": 0,
                    "evidence_ref": "e1",
                    "source_ref": "https://example.org/report",
                    "locator": {"section": "Evaluation"},
                }
            ],
            "conflicts": ["两份来源的测试范围不同。"],
            "unknowns": ["独立复核结果尚未公开。"],
            "assumptions": ["测试环境与所述部署一致。"],
            "stop_reason": "partial_evidence",
            **overrides,
        }
    )


def test_html_report_preserves_narrative_boundaries_and_clickable_sources():
    html = render_report_html(report())
    tree = HTMLParser(html)
    root = tree.css_first("html")
    assert root is not None
    assert root.attributes["lang"] == "zh-CN"
    assert "厂商称测试已完成" in tree.text()
    for text in ("两份来源的测试范围不同", "独立复核结果尚未公开", "测试环境与所述部署一致"):
        assert text in tree.text()
    assert tree.css_first('a[href="https://example.org/report"]') is not None
    assert tree.css_first('a[href="#source-1"]') is not None
    assert "@media print" in html
    assert "case_revision" not in tree.text()


def test_html_report_escapes_model_text_and_rejects_active_links():
    html = render_report_html(
        report(
            report_paragraphs=[{"text": '<img src=x onerror="alert(1)"><script>bad()</script>'}],
            citations=[
                {"conclusion_index": 0, "evidence_ref": "e1", "source_ref": "javascript:alert(1)"}
            ],
        )
    )
    tree = HTMLParser(html)
    assert not tree.css("script,img,iframe,form")
    assert not tree.css('a[href^="javascript:"]')
    assert "&lt;img" in html


def test_html_legacy_decision_uses_typed_conclusions_when_no_paragraphs():
    html = render_report_html(report(report_paragraphs=[]))
    assert "厂商报告了测试结果" in html
    assert "事实" in html


def test_html_layout_rejects_out_of_range_sections_on_legacy_read():
    html = render_report_html(
        report(
            report_layout={
                "title": "模型测试的证据边界",
                "sections": [{"heading": "遗漏", "paragraph_indices": [8]}],
            }
        )
    )
    assert "厂商称测试已完成" in html
    assert "独立复核结果尚未公开" in html


def test_report_collapses_same_document_sources_without_losing_evidence_coordinates():
    from packages.reasoning.report_html import ReportSource

    value = report(
        citations=[
            {"conclusion_index": 0, "evidence_ref": ref, "source_ref": "https://example.org/report"}
            for ref in ("e1", "e2")
        ],
        report_paragraphs=[{"text": "两段证据支持同一判断。", "evidence_refs": ["e1", "e2"]}],
    )
    sources = [
        ReportSource(
            evidence_ref=ref,
            label="Test report",
            url="https://example.org/report",
            revision_id="rev-1",
        )
        for ref in ("e1", "e2")
    ]
    tree = HTMLParser(render_report_html(value, sources=sources))
    assert len(tree.css(".source")) == 1
    assert len(tree.css("article > p .notes a")) == 1
    assert {node.attributes["data-evidence-ref"] for node in tree.css("[data-evidence-ref]")} == {
        "e1",
        "e2",
    }
    assert "2026年10月15日 08:00" in tree.text()


def test_grouped_source_notes_preserve_each_paragraphs_exact_chunk_and_section():
    from packages.reasoning.report_html import ReportSource

    sources = [
        ReportSource(
            evidence_ref=ref,
            label="Test report",
            url="https://example.org/report",
            revision_id="rev-1",
            detail=section,
        )
        for ref, section in (("e1", "Evaluation"), ("e2", "Limitations"))
    ]
    citations = [
        {"conclusion_index": 0, "evidence_ref": ref, "source_ref": "https://example.org/report"}
        for ref in ("e1", "e2")
    ]
    htmls = [
        render_report_html(
            report(
                citations=citations,
                report_paragraphs=[{"text": "同样文字引用不同证据片段。", "evidence_refs": [ref]}],
            ),
            sources=sources,
        )
        for ref in ("e1", "e2")
    ]
    assert htmls[0] != htmls[1]
    for ref, html in zip(("e1", "e2"), htmls, strict=True):
        tree = HTMLParser(html)
        note = tree.css_first("article > p .notes a")
        assert note is not None
        assert note.attributes["data-evidence-refs"] == f'["{ref}"]'
        assert "Evaluation" in tree.text() and "Limitations" in tree.text()


def test_summary_is_escaped_cited_and_precedes_body():
    html = render_report_html(
        report(report_summary={"text": "摘要 <script>内容</script>", "evidence_refs": ["e1"]})
    )
    tree = HTMLParser(html)
    assert tree.css_first(".report-summary .notes a") is not None
    assert not tree.css("script")
    assert html.index("摘要 &lt;script&gt;") < html.index("厂商称测试已完成")
