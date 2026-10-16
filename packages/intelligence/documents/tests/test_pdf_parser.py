from types import SimpleNamespace

from packages.intelligence.documents.parsers import PDFDocumentParser


def test_pdf_text_repairs_surrogate_pairs_without_losing_valid_characters(monkeypatch) -> None:
    extracted = "Agent \ud83d\udd12 security 中文; broken \ud800; null \x00; science \U0001d6fc"
    monkeypatch.setattr(
        "packages.intelligence.documents.parsers.PdfReader",
        lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: extracted)]),
    )
    sections = PDFDocumentParser().parse(b"synthetic PDF extraction boundary")
    assert len(sections) == 1
    assert sections[0].text == "Agent 🔒 security 中文; broken �; null ; science \U0001d6fc"
    assert sections[0].text.encode("utf-8").decode("utf-8") == sections[0].text
    assert sections[0].page_number == 1
