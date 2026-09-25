from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    page_number: int | None = None
    section: str | None = None


class ManagedDocumentParser(Protocol):
    NAME: str
    VERSION: str

    def parse(self, body: bytes) -> list[ParsedSection]: ...


class PDFDocumentParser:
    NAME = "pypdf"
    VERSION = "1"

    def parse(self, body: bytes) -> list[ParsedSection]:
        reader = PdfReader(BytesIO(body))
        sections: list[ParsedSection] = []
        for index, page in enumerate(reader.pages, start=1):
            text = _normalize_text(page.extract_text() or "")
            if text:
                sections.append(ParsedSection(text=text, page_number=index))
        return sections


class PlainTextDocumentParser:
    NAME = "plain-text"
    VERSION = "1"

    def parse(self, body: bytes) -> list[ParsedSection]:
        text = _normalize_text(body.decode("utf-8"))
        return [ParsedSection(text=text)] if text else []


def _normalize_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.replace("\x00", "").splitlines()]
    paragraphs = [line for line in lines if line]
    return "\n".join(paragraphs)
