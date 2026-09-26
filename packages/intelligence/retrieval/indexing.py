from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.contracts import EmbeddingProvider
from packages.intelligence.storage.document_models import DocumentChunkModel


class DocumentIndexBuildResult(BaseModel):
    document_revision_id: str
    lexical_index_version: str
    indexed_chunk_ids: list[str]
    changed: bool


class DocumentDenseIndexBuildResult(BaseModel):
    document_revision_id: str
    embedding_model: str
    embedding_version: str
    dimensions: int
    indexed_chunk_ids: list[str]
    changed: bool


class DocumentIndexService:
    """Prepare durable document chunks for downstream retrieval.

    PostgreSQL owns the physical FTS index and pgvector column. This service
    owns per-chunk capability state so M4 can distinguish lexical-only,
    dense-only, and fully retrieval-ready chunks without owning M3 indexing.
    """

    LEXICAL_INDEX_VERSION = "postgres-fts-simple-v1"

    async def build_lexical_index(
        self,
        session: AsyncSession,
        *,
        document_revision_id: str,
    ) -> DocumentIndexBuildResult:
        chunks = await _chunks(session, document_revision_id)
        changed = False
        chunk_ids: list[str] = []
        for chunk in chunks:
            chunk_ids.append(chunk.chunk_id)
            metadata = dict(chunk.metadata_json)
            if metadata.get("lexical_index_version") != self.LEXICAL_INDEX_VERSION:
                metadata["lexical_index_version"] = self.LEXICAL_INDEX_VERSION
                chunk.metadata_json = metadata
                changed = True
            next_status = _with_lexical(chunk.index_status)
            if chunk.index_status != next_status:
                chunk.index_status = next_status
                changed = True
        await session.flush()
        return DocumentIndexBuildResult(
            document_revision_id=document_revision_id,
            lexical_index_version=self.LEXICAL_INDEX_VERSION,
            indexed_chunk_ids=chunk_ids,
            changed=changed,
        )

    async def build_dense_index(
        self,
        session: AsyncSession,
        *,
        document_revision_id: str,
        provider: EmbeddingProvider,
    ) -> DocumentDenseIndexBuildResult:
        chunks = await _chunks(session, document_revision_id)
        batch = await provider.embed([chunk.text for chunk in chunks])
        if batch.dimensions <= 0:
            raise ValueError("embedding dimensions must be positive")
        if len(batch.vectors) != len(chunks):
            raise ValueError("embedding provider returned a different vector count")
        for vector in batch.vectors:
            if len(vector) != batch.dimensions:
                raise ValueError("embedding provider returned inconsistent dimensions")

        changed = False
        chunk_ids: list[str] = []
        for chunk, vector in zip(chunks, batch.vectors, strict=True):
            chunk_ids.append(chunk.chunk_id)
            metadata = dict(chunk.metadata_json)
            previous_dimensions = metadata.get("embedding_dimensions")
            if (
                chunk.embedding_model != batch.model
                or chunk.embedding_version != batch.version
                or previous_dimensions != batch.dimensions
                or list(chunk.embedding or []) != vector
            ):
                chunk.embedding = vector
                chunk.embedding_model = batch.model
                chunk.embedding_version = batch.version
                metadata["embedding_dimensions"] = batch.dimensions
                chunk.metadata_json = metadata
                changed = True
            next_status = _with_dense(chunk.index_status)
            if chunk.index_status != next_status:
                chunk.index_status = next_status
                changed = True
        await session.flush()
        return DocumentDenseIndexBuildResult(
            document_revision_id=document_revision_id,
            embedding_model=batch.model,
            embedding_version=batch.version,
            dimensions=batch.dimensions,
            indexed_chunk_ids=chunk_ids,
            changed=changed,
        )


async def _chunks(
    session: AsyncSession,
    document_revision_id: str,
) -> list[DocumentChunkModel]:
    chunks = list(
        await session.scalars(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_revision_id == document_revision_id)
            .order_by(DocumentChunkModel.ordinal, DocumentChunkModel.chunk_id)
        )
    )
    if not chunks:
        raise LookupError(f"document revision has no chunks: {document_revision_id}")
    return chunks


def _with_lexical(status: str) -> str:
    if status == "pending":
        return "lexical_ready"
    if status == "dense_ready":
        return "retrieval_ready"
    return status


def _with_dense(status: str) -> str:
    if status == "pending":
        return "dense_ready"
    if status == "lexical_ready":
        return "retrieval_ready"
    return status
