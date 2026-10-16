from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import ClassVar, Protocol

from pypdf import PdfReader
from selectolax.parser import HTMLParser, Node


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
    VERSION = "3"

    def parse(self, body: bytes) -> list[ParsedSection]:
        reader = PdfReader(BytesIO(body))
        sections: list[ParsedSection] = []
        for index, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text() or ""
            # Some PDF character maps emit UTF-16 surrogate code units instead
            # of Unicode scalars. Recombine valid pairs, mark isolated units,
            # and retain the original PDF as the evidence authority.
            safe_text = extracted.encode("utf-16-le", errors="surrogatepass").decode(
                "utf-16-le", errors="replace"
            )
            text = _normalize_text(safe_text)
            if text:
                sections.append(ParsedSection(text=text, page_number=index))
        return sections


class HTMLDocumentParser:
    NAME = "selectolax-html"
    VERSION = "7"

    _DROP_SELECTOR = (
        "script,style,noscript,nav,footer,aside,form,svg,canvas,"
        "[role=navigation],[role=banner],.related-posts"
    )
    _CONTENT_SELECTORS = (
        ".text--blog-content",
        ".blog-content",
        ".entry-content",
        ".post-content",
        "article",
        "main",
        "[role=main]",
    )
    _BLOCK_TAGS: ClassVar[frozenset[str]] = frozenset(
        {"p", "li", "pre", "blockquote", "tr", "dt", "dd"}
    )
    _HEADING_TAGS: ClassVar[frozenset[str]] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    def parse(self, body: bytes) -> list[ParsedSection]:
        tree = HTMLParser(body.decode("utf-8", errors="replace"))
        for node in tree.css(self._DROP_SELECTOR):
            node.decompose()

        for node in tree.css("header"):
            parent = node.parent
            while parent is not None and parent.tag not in {"article", "main"}:
                parent = parent.parent
            if parent is None:
                node.decompose()
        # Remove only the small, explicit extension-install widget. Never remove
        # an article merely for mentioning the extension in research prose.
        for node in reversed(tree.css("div,section")):
            value = " ".join(node.text(separator=" ", strip=True).split()).casefold()
            if (
                len(value) < 500
                and value.startswith("webflow input enhancer")
                and "this project uses the webflow input enhancer extension" in value
                and "recommend installing it" in value
            ):
                node.decompose()

        # Selector groups follow document order, which can choose a related-post
        # card before the actual article body. Prefer the known content container.
        root: Node | None = None
        for selector in self._CONTENT_SELECTORS:
            candidates = tree.css(selector)
            root = max(
                candidates,
                key=lambda node: (node.css_first("h1") is not None, len(node.text(strip=True))),
                default=None,
            )
            if root is not None:
                break
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
        for node in root.traverse(include_text=False):
            # selectolax traversal can continue into the selected root's siblings.
            ancestor: Node | None = node
            while ancestor is not None and ancestor != root:
                ancestor = ancestor.parent
            if ancestor is None:
                break
            tag = node.tag.lower() if isinstance(node.tag, str) else ""
            if tag in self._HEADING_TAGS:
                flush()
                heading = _normalize_text(node.text(separator=" ", strip=True))
                current_heading = heading or current_heading
                last_block = None
                continue
            if tag not in self._BLOCK_TAGS and tag != "div":
                continue
            if tag == "div":
                # Some sources place evidence/notice labels in leaf divs next to
                # paragraphs. Preserve those, but never flatten enclosing layout
                # containers (which would duplicate text and lose headings).
                structural = ",".join(self._BLOCK_TAGS | self._HEADING_TAGS | {"div", "section"})
                if any(
                    child.css_first(structural) is not None
                    for child in node.iter(include_text=False)
                ):
                    continue
            parent = node.parent
            nested_block = False
            while parent is not None and parent != root:
                if parent.tag in self._BLOCK_TAGS:
                    nested_block = True
                    break
                parent = parent.parent
            if nested_block:
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
    VERSION = "2"

    def parse(self, body: bytes) -> list[ParsedSection]:
        text = _normalize_text(body.decode("utf-8"))
        return [ParsedSection(text=text)] if text else []


def _normalize_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.replace("\x00", "").splitlines()]
    paragraphs = [line for line in lines if line]
    return "\n".join(paragraphs)
