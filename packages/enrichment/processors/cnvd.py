from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from packages.intelligence.knowledge.contracts import ClaimCandidate, EnrichmentCandidate
from packages.sources.contracts import IngestEnvelope
from packages.sources.errors import SourceSchemaChanged

_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_CNVD_RE = re.compile(r"\bCNVD-\d{4}-\d{3,}\b", re.IGNORECASE)


class CNVDHTMLMapper:
    """Extract stable CNVD/CVE identity from an explicitly fetched CNVD detail page."""

    PROCESSOR_NAME = "cnvd-reference-enrichment"
    PROCESSOR_VERSION = "1"

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate:
        if envelope.media_type not in {"text/html", "application/xhtml+xml"}:
            raise SourceSchemaChanged("CNVD reference requires an HTML detail page")
        tree = HTMLParser(envelope.content_bytes())
        root = tree.body or tree.root
        if root is None:
            raise SourceSchemaChanged("CNVD detail page has no parseable HTML root")
        text = " ".join(root.text(separator=" ", strip=True).split())
        cve_ids = sorted({item.upper() for item in _CVE_RE.findall(text)})
        cnvd_ids = sorted({item.upper() for item in _CNVD_RE.findall(text)})
        if len(cve_ids) != 1:
            raise SourceSchemaChanged(
                f"CNVD detail page must expose exactly one CVE id; found={cve_ids!r}"
            )
        if len(cnvd_ids) != 1:
            raise SourceSchemaChanged(
                f"CNVD detail page must expose exactly one CNVD id; found={cnvd_ids!r}"
            )

        title_node = tree.css_first("h1") or tree.css_first("title")
        title = (
            " ".join(title_node.text(separator=" ", strip=True).split())
            if title_node is not None
            else None
        )
        claims = [
            ClaimCandidate(
                predicate="cnvd_id",
                value=cnvd_ids[0],
                locator={"kind": "html_text", "match": cnvd_ids[0]},
            )
        ]
        if title:
            claims.append(
                ClaimCandidate(
                    predicate="cnvd_title",
                    value=title,
                    locator={"kind": "html_selector", "selector": "h1|title"},
                )
            )
        return EnrichmentCandidate(
            root_identifiers={
                "cve": cve_ids,
                "cnvd": cnvd_ids,
            },
            claims=claims,
            replace_predicates=["cnvd_id", "cnvd_title"],
        )
