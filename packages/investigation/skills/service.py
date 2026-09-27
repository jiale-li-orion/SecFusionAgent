from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.skills.contracts import (
    SkillManifest,
    SkillProcedure,
    SkillProvenance,
    SkillStatus,
    SkillStepFragment,
    SkillVersion,
)
from packages.investigation.skills.storage import SkillVersionModel


class SkillStore:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def publish(self, session: AsyncSession, skill: SkillVersion) -> SkillVersion:
        _validate_procedure_portability(skill)
        identity = _skill_version_id(skill.manifest.skill_id, skill.manifest.version)
        digest = _content_hash(skill)
        existing = await session.get(SkillVersionModel, identity)
        if existing is not None:
            if existing.content_hash != digest:
                raise ValueError("SkillVersion identity is immutable")
            return _view(existing)
        model = SkillVersionModel(
            skill_version_id=identity,
            skill_id=skill.manifest.skill_id,
            version=skill.manifest.version,
            namespace=skill.manifest.namespace,
            status=skill.manifest.status.value,
            source_type=skill.manifest.source_type.value,
            manifest_json=skill.manifest.model_dump(mode="json"),
            procedure_json=skill.procedure.model_dump(mode="json"),
            provenance_json=skill.provenance.model_dump(mode="json"),
            content_hash=digest,
            validation_ref=skill.manifest.validation_ref,
            supersedes=skill.manifest.supersedes,
            created_at=self._now(),
        )
        session.add(model)
        await session.flush()
        return _view(model)

    async def get(self, session: AsyncSession, skill_ref: str) -> SkillVersion:
        skill_id, version = parse_skill_ref(skill_ref)
        model = await session.scalar(
            select(SkillVersionModel).where(
                SkillVersionModel.skill_id == skill_id,
                SkillVersionModel.version == version,
            )
        )
        if model is None:
            raise LookupError(f"skill version not found: {skill_ref}")
        return _view(model)

    async def list_namespace(
        self,
        session: AsyncSession,
        namespaces: set[str],
    ) -> list[SkillVersion]:
        if not namespaces:
            return []
        rows = list(
            await session.scalars(
                select(SkillVersionModel)
                .where(SkillVersionModel.namespace.in_(sorted(namespaces)))
                .order_by(SkillVersionModel.skill_id, SkillVersionModel.version.desc())
            )
        )
        latest: dict[str, SkillVersionModel] = {}
        for row in rows:
            latest.setdefault(row.skill_id, row)
        return [_view(row) for row in latest.values()]

    async def search_manifests(
        self,
        session: AsyncSession,
        *,
        namespaces: set[str],
        statuses: set[SkillStatus] | None = None,
    ) -> list[SkillManifest]:
        allowed_statuses = statuses or {SkillStatus.VALIDATED, SkillStatus.ACTIVE}
        skills = await self.list_namespace(session, namespaces)
        return [skill.manifest for skill in skills if skill.manifest.status in allowed_statuses]

    async def get_procedure(self, session: AsyncSession, skill_ref: str) -> SkillProcedure:
        return (await self.get(session, skill_ref)).procedure

    async def get_step(
        self,
        session: AsyncSession,
        skill_ref: str,
        step_id: str,
    ) -> SkillStepFragment:
        procedure = await self.get_procedure(session, skill_ref)
        for step in procedure.steps:
            if step.step_id == step_id:
                return step
        raise LookupError(f"skill step not found: {skill_ref}#{step_id}")

    async def get_provenance(self, session: AsyncSession, skill_ref: str) -> SkillProvenance:
        return (await self.get(session, skill_ref)).provenance


def parse_skill_ref(skill_ref: str) -> tuple[str, int]:
    if not skill_ref.startswith("skill:"):
        raise ValueError(f"invalid skill ref: {skill_ref}")
    identity, separator, version_text = skill_ref.removeprefix("skill:").rpartition("@")
    if not separator or not identity or not version_text.isdigit():
        raise ValueError(f"invalid skill ref: {skill_ref}")
    return identity, int(version_text)


def _view(model: SkillVersionModel) -> SkillVersion:
    return SkillVersion.model_validate(
        {
            "manifest": model.manifest_json,
            "procedure": model.procedure_json,
            "provenance": model.provenance_json,
        }
    )


def _content_hash(skill: SkillVersion) -> str:
    payload = skill.model_dump(mode="json")
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _skill_version_id(skill_id: str, version: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:skill:{skill_id}@{version}"))


_FORBIDDEN_IMPLEMENTATION_HINTS = (
    "://",
    "curl ",
    "wget ",
    "gh api",
    "mcp tool",
    "/bin/",
    "docker.sock",
)


def _validate_procedure_portability(skill: SkillVersion) -> None:
    texts = [
        *(step.semantic_instruction for step in skill.procedure.steps),
        *skill.procedure.failure_guards,
        *skill.procedure.fallbacks,
        *skill.procedure.stop_conditions,
    ]
    lowered = "\n".join(texts).lower()
    leaked = [hint for hint in _FORBIDDEN_IMPLEMENTATION_HINTS if hint in lowered]
    if leaked:
        raise ValueError(
            "SkillProcedure must remain implementation-agnostic; forbidden hints: "
            + ",".join(leaked)
        )
