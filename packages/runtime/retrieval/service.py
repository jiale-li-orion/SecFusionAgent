from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.retrieval.contracts import (
    RetrievalDisposition,
    RetrievalInvocation,
    RetrievalRequestCoordinate,
)
from packages.runtime.retrieval.storage import RetrievalInvocationModel


class RetrievalInvocationService:
    async def find_reusable(
        self,
        session: AsyncSession,
        *,
        product_session_id: str,
        before_turn_index: int,
        request: RetrievalRequestCoordinate,
    ) -> RetrievalInvocation | None:
        model = await session.scalar(
            select(RetrievalInvocationModel)
            .where(
                RetrievalInvocationModel.product_session_id == product_session_id,
                RetrievalInvocationModel.product_turn_index < before_turn_index,
                RetrievalInvocationModel.request_digest == request.request_digest,
                RetrievalInvocationModel.disposition.in_((
                    RetrievalDisposition.EXECUTED.value,
                    RetrievalDisposition.REUSED.value,
                )),
            )
            .order_by(
                RetrievalInvocationModel.product_turn_index.desc(),
                RetrievalInvocationModel.finished_at.desc(),
            )
            .limit(1)
        )
        return _view(model) if model is not None else None

    async def record(
        self,
        session: AsyncSession,
        *,
        request_owner_ref: str,
        product_session_id: str,
        product_turn_index: int,
        request: RetrievalRequestCoordinate,
        result_refs: list[str],
        disposition: RetrievalDisposition,
        reuse_of_invocation_id: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> RetrievalInvocation:
        if disposition is RetrievalDisposition.FAILED:
            raise ValueError("failed retrieval requires record_failed")
        if disposition is RetrievalDisposition.REUSED and reuse_of_invocation_id is None:
            raise ValueError("reused retrieval invocation requires reuse_of_invocation_id")
        if disposition is RetrievalDisposition.EXECUTED and reuse_of_invocation_id is not None:
            raise ValueError("executed retrieval invocation cannot name reuse_of_invocation_id")
        instant = finished_at or datetime.now(UTC)
        model = RetrievalInvocationModel(
            invocation_id=str(uuid4()),
            request_owner_ref=request_owner_ref,
            product_session_id=product_session_id,
            product_turn_index=product_turn_index,
            operator=request.operator,
            operator_revision=request.operator_revision,
            query_digest=request.query_digest,
            request_digest=request.request_digest,
            knowledge_revision=request.knowledge_revision,
            result_limit=request.limit,
            source_ids=list(request.source_ids),
            result_refs=list(result_refs),
            result_count=len(result_refs),
            disposition=disposition.value,
            reuse_of_invocation_id=reuse_of_invocation_id,
            started_at=started_at or instant,
            finished_at=instant,
        )
        session.add(model)
        await session.flush()
        return _view(model)

    async def record_failed(
        self,
        session: AsyncSession,
        *,
        request_owner_ref: str,
        product_session_id: str,
        product_turn_index: int,
        request: RetrievalRequestCoordinate,
        failure_class: str,
        started_at: datetime,
    ) -> RetrievalInvocation:
        model = RetrievalInvocationModel(
            invocation_id=str(uuid4()),
            request_owner_ref=request_owner_ref,
            product_session_id=product_session_id,
            product_turn_index=product_turn_index,
            operator=request.operator,
            operator_revision=request.operator_revision,
            query_digest=request.query_digest,
            request_digest=request.request_digest,
            knowledge_revision=request.knowledge_revision,
            result_limit=request.limit,
            source_ids=list(request.source_ids),
            result_refs=[],
            result_count=0,
            disposition=RetrievalDisposition.FAILED.value,
            failure_class=failure_class[:128],
            reuse_of_invocation_id=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        session.add(model)
        await session.flush()
        return _view(model)


def _view(model: RetrievalInvocationModel) -> RetrievalInvocation:
    return RetrievalInvocation(
        invocation_id=model.invocation_id,
        request_owner_ref=model.request_owner_ref,
        product_session_id=model.product_session_id,
        product_turn_index=model.product_turn_index,
        request=RetrievalRequestCoordinate(
            operator=model.operator,
            operator_revision=model.operator_revision,
            query_digest=model.query_digest,
            knowledge_revision=model.knowledge_revision,
            limit=model.result_limit,
            source_ids=list(model.source_ids),
        ),
        result_refs=list(model.result_refs),
        disposition=RetrievalDisposition(model.disposition),
        reuse_of_invocation_id=model.reuse_of_invocation_id,
        failure_class=model.failure_class,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )
