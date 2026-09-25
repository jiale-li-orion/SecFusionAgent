from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from packages.intelligence.documents.parsers import ParsedSection


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    ordinal: int
    text: str
    page_number: int | None
    section: str | None
    char_start: int
    char_end: int
    content_hash: str


def chunk_sections(
    sections: list[ParsedSection],
    *,
    chunk_size: int = 3500,
    overlap: int = 350,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    chunks: list[DocumentChunk] = []
    ordinal = 0
    step = chunk_size - overlap
    for section in sections:
        text = section.text.strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        ordinal=ordinal,
                        text=chunk_text,
                        page_number=section.page_number,
                        section=section.section,
                        char_start=start,
                        char_end=end,
                        content_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
                    )
                )
                ordinal += 1
            if end == len(text):
                break
            start += step
    return chunks
