from __future__ import annotations

from email.utils import parsedate_to_datetime
from hashlib import sha256
from urllib.parse import urlparse

import httpx
from pydantic import JsonValue

from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    DiscoveryBatch,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
    SourceState,
)
from packages.sources.errors import SourceFetchFailed, SourceRateLimited, SourceSchemaChanged


class DirectDocumentAdapter:
    """Acquire a bounded registry of known authoritative documents.

    Discovery is configuration-driven; every scheduled run rechecks each URL so
    mutable official documents can produce a new Observation when content or
    HTTP revision metadata changes. EvidenceIngress absorbs exact replay.
    """

    USER_AGENT = "SecFusionAgent/0.1 authoritative-document-monitor"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del state
        documents = source.discovery_method.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError("direct_document source requires discovery_method.documents")
        allowed_hosts = _allowed_hosts(source)
        refs: list[DiscoveredRef] = []
        for item in documents:
            if not isinstance(item, dict):
                raise ValueError("direct_document document entry must be an object")
            url = item.get("url")
            if not isinstance(url, str) or not _is_allowed_url(url, allowed_hosts):
                raise ValueError("direct_document URL is outside configured allowed_hosts")
            title = item.get("title")
            document_id = item.get("document_id")
            external_id = (
                document_id
                if isinstance(document_id, str) and document_id
                else f"url:{sha256(url.encode()).hexdigest()}"
            )
            locator: dict[str, JsonValue] = {"url": url}
            if isinstance(title, str) and title:
                locator["title"] = title
            kind = item.get("document_type")
            if isinstance(kind, str) and kind:
                locator["document_type"] = kind
            refs.append(
                DiscoveredRef(
                    external_object_id=external_id,
                    canonical_url=url,
                    locator=locator,
                )
            )
        return DiscoveryBatch(items=refs, next_cursor={"configured_documents": len(refs)})

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if not ref.canonical_url:
            raise SourceSchemaChanged("direct_document ref has no URL")
        if not _is_allowed_url(ref.canonical_url, _allowed_hosts(source)):
            raise ValueError("direct_document URL is outside configured allowed_hosts")
        try:
            response = await self._client.get(
                ref.canonical_url,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT, "Accept": "*/*"},
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"direct document request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("direct document source rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"direct document source returned HTTP {response.status_code}")
        media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not media_type:
            media_type = _guess_media_type(str(response.url))
        allowed_media_types = _allowed_media_types(source)
        if media_type not in allowed_media_types:
            raise SourceSchemaChanged(
                f"direct document returned content type {media_type!r}; "
                f"allowed={sorted(allowed_media_types)!r}"
            )
        last_modified = response.headers.get("last-modified")
        updated_at = None
        if last_modified:
            try:
                updated_at = parsedate_to_datetime(last_modified)
            except (TypeError, ValueError):
                updated_at = None
        etag = response.headers.get("etag")
        metadata = dict(ref.locator)
        metadata["provider"] = source.source_family
        if etag:
            metadata["etag"] = etag
        if last_modified:
            metadata["last_modified"] = last_modified
        return IngestEnvelope.for_binary_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            body=response.content,
            media_type=media_type,
            canonical_url=str(response.url),
            published_at=None,
            updated_at=updated_at,
            external_revision=etag or last_modified,
            request_metadata=metadata,
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        document_id = spec.filters.get("document_id")
        url = spec.filters.get("url")
        batch = await self.discover(source, SourceState())
        matches = [
            ref
            for ref in batch.items
            if (isinstance(document_id, str) and ref.external_object_id == document_id)
            or (isinstance(url, str) and ref.canonical_url == url)
        ]
        if not matches:
            raise LookupError("configured direct document not found")
        return [
            await self.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            for ref in matches
        ]


def _allowed_hosts(source: SourceDefinition) -> set[str]:
    configured = source.discovery_method.get("allowed_hosts")
    if not isinstance(configured, list) or not configured:
        raise ValueError("direct_document source requires allowed_hosts")
    return {item.lower() for item in configured if isinstance(item, str) and item}


def _allowed_media_types(source: SourceDefinition) -> set[str]:
    configured = source.discovery_method.get("allowed_media_types")
    if configured is None:
        return {"text/html", "application/xhtml+xml", "application/pdf"}
    if not isinstance(configured, list):
        raise ValueError("direct_document allowed_media_types must be a list")
    return {item.lower() for item in configured if isinstance(item, str) and item}


def _is_allowed_url(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.hostname.lower() in allowed_hosts
    )


def _guess_media_type(url: str) -> str:
    return "application/pdf" if urlparse(url).path.lower().endswith(".pdf") else "text/html"
