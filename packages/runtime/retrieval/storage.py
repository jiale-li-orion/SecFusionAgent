from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class RetrievalInvocationModel(Base):
    __tablename__ = "retrieval_invocations"

    invocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_owner_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    product_session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_turn_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operator_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    query_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    knowledge_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    result_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reuse_of_invocation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("retrieval_invocations.invocation_id", ondelete="SET NULL"),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
