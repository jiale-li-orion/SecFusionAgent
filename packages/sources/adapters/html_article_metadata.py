"""Publication metadata asserted by an HTML article, with precision and origin."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urldefrag, urljoin

from pydantic import JsonValue
from selectolax.parser import HTMLParser

_ARTICLE_TYPES = {
    "Article",
    "NewsArticle",
    "BlogPosting",
    "ScholarlyArticle",
    "TechArticle",
    "Report",
}


@dataclass(frozen=True, slots=True)
class ArticleMetadata:
    title: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


def extract_article_metadata(body: bytes, *, page_url: str | None = None) -> ArticleMetadata:
    tree = HTMLParser(body.decode("utf-8", errors="replace"))
    metadata: dict[str, JsonValue] = {}
    for node in tree.css("aside,nav,footer,[role=navigation],[role=banner],.related-posts"):
        node.decompose()
    root = tree.body
    # Match the managed parser's article-container priority so article metadata
    # cannot be supplied by an unrelated sidebar or preview card.
    for selector in (".entry-content", ".post-content", "article", "main", "[role=main]"):
        nodes = tree.css(selector)
        if nodes:
            root = max(
                nodes,
                key=lambda node: (
                    node.css_first("h1") is not None,
                    len(node.text(strip=True)),
                ),
            )
            break
    if root is not None and root.tag not in {"article", "main", "body"}:
        parent = root.parent
        while parent is not None and parent.tag not in {"article", "body"}:
            parent = parent.parent
        if parent is not None and parent.tag == "article":
            root = parent
    title = None
    for selector in ("h1",):
        for node in root.css(selector) if root is not None else []:
            candidate = " ".join(node.text(separator=" ", strip=True).split())
            if 1 <= len(candidate) <= 250:
                title = candidate
                metadata["title_origin"] = "html:h1"
                break
        if title:
            break
    if title is None:
        for node in tree.css('meta[property="og:title"]'):
            candidate = " ".join((node.attributes.get("content") or "").split())
            if 1 <= len(candidate) <= 250:
                title = candidate
                metadata["title_origin"] = "html:og:title"
                break

    candidates: list[tuple[str, str]] = []
    for node in tree.css('meta[property="article:published_time"]'):
        candidates.append((node.attributes.get("content") or "", "html:article:published_time"))
    jsonld_dates: set[str] = set()
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        for article in _article_entities(payload):
            identity = article.get("mainEntityOfPage", article.get("url"))
            if isinstance(identity, dict):
                identity = identity.get("@id")
            if page_url and isinstance(identity, str):
                if urldefrag(urljoin(page_url, identity))[0].rstrip("/") != (
                    urldefrag(page_url)[0].rstrip("/")
                ):
                    continue
            value = article.get("datePublished")
            if isinstance(value, str):
                jsonld_dates.add(value)
    if len(jsonld_dates) == 1:
        candidates.append((next(iter(jsonld_dates)), "html:jsonld:datePublished"))
    # A lone time can describe an update, event, or deadline. Only explicit
    # publication semantics may establish article publication.
    times = (
        root.css('time[itemprop="datePublished"],time[pubdate],time.published')
        if root is not None
        else []
    )
    for node in times:
        candidates.append((node.attributes.get("datetime") or "", "html:time"))

    for origin in dict.fromkeys(origin for _, origin in candidates):
        valid = {
            raw.strip(): _publication(raw)
            for raw, source in candidates
            if source == origin and _publication(raw) is not None
        }
        if len(set(valid.values())) > 1:
            return ArticleMetadata(title, metadata=metadata)
        if not valid:
            continue
        raw, parsed = next(iter(valid.items()))
        if parsed is None:
            continue
        published_at, precision, published_date = parsed
        metadata.update(
            {
                "published_at_origin": origin,
                "published_at_raw": raw,
                "published_at_precision": precision,
            }
        )
        if published_date:
            metadata["published_date"] = published_date
        return ArticleMetadata(title, published_at, metadata)
    return ArticleMetadata(title, metadata=metadata)


def _article_entities(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [article for item in value for article in _article_entities(item)]
    if not isinstance(value, dict):
        return []
    types = value.get("@type", [])
    types = [types] if isinstance(types, str) else types
    articles = (
        [value]
        if isinstance(types, list)
        and any(
            isinstance(kind, str) and kind.rsplit("/", 1)[-1] in _ARTICLE_TYPES for kind in types
        )
        else []
    )
    # Do not recursively mine arbitrary properties such as related events/offers.
    return (
        articles
        + _article_entities(value.get("@graph"))
        + _article_entities(value.get("mainEntity"))
    )


def _publication(raw: str) -> tuple[datetime | None, str, str | None] | None:
    value = raw.strip()
    try:
        if len(value) == 10:
            return None, "date", date.fromisoformat(value).isoformat()
        if "T" not in value and " " not in value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, "local_datetime", None
    return parsed, "datetime", None
