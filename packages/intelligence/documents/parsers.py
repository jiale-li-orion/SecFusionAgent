from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import ClassVar, Protocol

from pypdf import PdfReader
from selectolax.parser import HTMLParser


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    page_number: int | None = None
    section: str | None = None
    source_locator: dict[str, object] = field(default_factory=dict)


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


class HTMLDocumentParser:
    NAME = "selectolax-html"
    VERSION = "1"

    _DROP_SELECTOR = "script,style,noscript,nav,header,footer,aside,form,svg,canvas"
    _CONTENT_SELECTOR = "article,main,[role=main]"
    _BLOCK_TAGS: ClassVar[frozenset[str]] = frozenset(
        {"p", "li", "pre", "blockquote", "tr", "dt", "dd"}
    )
    _HEADING_TAGS: ClassVar[frozenset[str]] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    def parse(self, body: bytes) -> list[ParsedSection]:
        tree = HTMLParser(body.decode("utf-8", errors="replace"))
        for node in tree.css(self._DROP_SELECTOR):
            node.decompose()

        root = tree.css_first(self._CONTENT_SELECTOR)
        if root is None:
            pre_nodes = tree.css("pre")
            if len(pre_nodes) == 1:
                pre_text = _normalize_text(pre_nodes[0].text(separator="\n", strip=True))
                body_text = (
                    _normalize_text(tree.body.text(separator="\n", strip=True))
                    if tree.body is not None
                    else ""
                )
                if len(pre_text) >= 200 and len(pre_text) >= max(1, len(body_text) // 3):
                    return [
                        ParsedSection(
                            text=pre_text,
                            source_locator={
                                "kind": "html_preformatted_document",
                                "section_index": 0,
                            },
                        )
                    ]
            root = tree.body
        if root is None:
            return []

        sections: list[ParsedSection] = []
        current_heading: str | None = None
        buffer: list[str] = []
        section_index = 0

        def flush() -> None:
            nonlocal buffer, section_index
            if not buffer:
                return
            text = _normalize_text("\n".join(buffer))
            buffer = []
            if not text:
                return
            sections.append(
                ParsedSection(
                    text=text,
                    section=current_heading,
                    source_locator={
                        "kind": "html_section",
                        "heading": current_heading,
                        "section_index": section_index,
                    },
                )
            )
            section_index += 1

        last_block: str | None = None
        for node in root.iter(include_text=False):
            tag = node.tag.lower() if isinstance(node.tag, str) else ""
            if tag in self._HEADING_TAGS:
                flush()
                heading = _normalize_text(node.text(separator=" ", strip=True))
                current_heading = heading or current_heading
                last_block = None
                continue
            if tag not in self._BLOCK_TAGS:
                continue
            value = _normalize_text(node.text(separator=" ", strip=True))
            if not value or value == last_block:
                continue
            buffer.append(value)
            last_block = value
        flush()

        if sections:
            return sections
        fallback = _normalize_text(root.text(separator="\n", strip=True))
        return (
            [
                ParsedSection(
                    text=fallback,
                    source_locator={"kind": "html_document", "section_index": 0},
                )
            ]
            if fallback
            else []
        )


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
