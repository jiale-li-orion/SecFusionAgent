from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, JsonValue, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.model_provider import StructuredModelRequest
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
)


class FragmentCacheClass(StrEnum):
    STATIC = "static"
    TASK_STABLE = "task_stable"
    STATE_DYNAMIC = "state_dynamic"
    EPHEMERAL = "ephemeral"


_CACHE_ORDER = {
    FragmentCacheClass.STATIC: 0,
    FragmentCacheClass.TASK_STABLE: 1,
    FragmentCacheClass.STATE_DYNAMIC: 2,
    FragmentCacheClass.EPHEMERAL: 3,
}


class FragmentTrustClass(StrEnum):
    PLATFORM_INVARIANT = "platform_invariant"
    RUNTIME_CONTROL = "runtime_control"
    PROCEDURAL = "procedural"
    PROCEDURAL_PROVENANCE = "procedural_provenance"
    DURABLE_STATE = "durable_state"
    EVIDENCE_REFERENCE = "evidence_reference"
    UNTRUSTED_EXTERNAL = "untrusted_external"


_INSTRUCTION_TRUST = frozenset(
    {
        FragmentTrustClass.PLATFORM_INVARIANT,
        FragmentTrustClass.RUNTIME_CONTROL,
        FragmentTrustClass.PROCEDURAL,
    }
)


class MaterializedFragment(BaseModel):
    fragment_id: str
    kind: str
    source_ref: str
    source_revision: str
    disclosure_level: str | None = None
    selection_reason: str | None = None
    trust_class: FragmentTrustClass
    cache_class: FragmentCacheClass
    content_hash: str
    content: JsonValue

    @model_validator(mode="after")
    def validate_fragment(self) -> MaterializedFragment:
        for value, label in (
            (self.fragment_id, "fragment_id"),
            (self.kind, "kind"),
            (self.source_ref, "source_ref"),
            (self.source_revision, "source_revision"),
            (self.content_hash, "content_hash"),
        ):
            if not value.strip():
                raise ValueError(f"MaterializedFragment {label} cannot be empty")
        if self.content_hash != _content_hash(self.content):
            raise ValueError("MaterializedFragment content_hash does not match content")
        return self

    @classmethod
    def build(
        cls,
        *,
        kind: str,
        source_ref: str,
        source_revision: str,
        trust_class: FragmentTrustClass,
        cache_class: FragmentCacheClass,
        content: JsonValue,
        disclosure_level: str | None = None,
        selection_reason: str | None = None,
    ) -> MaterializedFragment:
        digest = _content_hash(content)
        identity = _digest(
            {
                "kind": kind,
                "source_ref": source_ref,
                "source_revision": source_revision,
                "disclosure_level": disclosure_level,
                "selection_reason": selection_reason,
                "trust_class": trust_class.value,
                "cache_class": cache_class.value,
                "content_hash": digest,
            }
        )
        return cls(
            fragment_id=str(uuid5(NAMESPACE_URL, f"secfusion:fragment:{identity}")),
            kind=kind,
            source_ref=source_ref,
            source_revision=source_revision,
            disclosure_level=disclosure_level,
            selection_reason=selection_reason,
            trust_class=trust_class,
            cache_class=cache_class,
            content_hash=digest,
            content=content,
        )


class PromptAssembly(BaseModel):
    assembly_id: str
    execution_id: str
    task_contract_id: str
    task_run_id: str
    role_revision: str
    context_manifest_revision: int = Field(ge=1)
    platform_invariant_revision: str
    execution_profile_revision: str
    policy_context_revision: str
    materialized_skill_refs: list[str] = Field(default_factory=list)
    materialized_capability_view_refs: list[str] = Field(default_factory=list)
    state_projection_revision: str | None = None
    percept_refs: list[str] = Field(default_factory=list)
    materialized_fragment_refs: list[str] = Field(default_factory=list)
    materialized_ref_set_digest: str
    ordered_fragment_ids: list[str]
    cache_handle_hints: list[str] = Field(default_factory=list)
    assembly_hash: str
    fragments: list[MaterializedFragment] = Field(default_factory=list)

    def to_model_request(self) -> StructuredModelRequest:
        by_id = {fragment.fragment_id: fragment for fragment in self.fragments}
        ordered = [by_id[fragment_id] for fragment_id in self.ordered_fragment_ids]
        instruction_fragments = [
            _fragment_payload(fragment)
            for fragment in ordered
            if fragment.trust_class in _INSTRUCTION_TRUST
        ]
        data_fragments = [
            _fragment_payload(fragment)
            for fragment in ordered
            if fragment.trust_class not in _INSTRUCTION_TRUST
        ]
        system_instruction = json.dumps(
            {
                "assembly_id": self.assembly_id,
                "instruction_fragments": instruction_fragments,
                "note": (
                    "Prompt instructions do not grant permission or factual authority; "
                    "runtime policy and state/evidence gates remain authoritative."
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return StructuredModelRequest(
            system_instruction=system_instruction,
            data={
                "assembly_id": self.assembly_id,
                "context_manifest_revision": self.context_manifest_revision,
                "data_fragments": cast(JsonValue, data_fragments),
                "percept_refs": cast(JsonValue, self.percept_refs),
            },
            metadata={
                "assembly_hash": self.assembly_hash,
                "materialized_ref_set_digest": self.materialized_ref_set_digest,
                "role_revision": self.role_revision,
            },
        )


class ContextMaterializer:
    def __init__(
        self,
        *,
        platform_invariant_revision: str,
        platform_invariant: dict[str, JsonValue],
    ) -> None:
        if not platform_invariant_revision.strip():
            raise ValueError("platform_invariant_revision cannot be empty")
        self._platform_revision = platform_invariant_revision
        self._platform_invariant = platform_invariant

    async def materialize(
        self,
        session: AsyncSession,
        *,
        task_run_id: str,
        dynamic_fragments: list[MaterializedFragment] | None = None,
        disclosure_fragments: list[MaterializedFragment] | None = None,
        ephemeral_fragments: list[MaterializedFragment] | None = None,
        runtime_disclosure_refs: set[str] | None = None,
        percept_refs: list[str] | None = None,
        execution_profile_revision: str | None = None,
        state_projection_revision: str | None = None,
    ) -> PromptAssembly:
        run = await get_task_run(session, task_run_id)
        contract = await get_task_contract_for_run(session, task_run_id)
        manifest = await get_task_context(session, task_run_id)
        role = canonical_roles().get(run.role_id)
        if role is None or role.version != run.role_version:
            raise ValueError(f"unknown or mismatched RoleProfile: {run.role_id}@{run.role_version}")
        resolved_execution_profile_revision = (
            execution_profile_revision or f"{role.default_execution_profile.value}@1"
        )
        resolved_execution_profile = resolved_execution_profile_revision.partition("@")[0]

        builtins = [
            MaterializedFragment.build(
                kind="platform_invariant",
                source_ref="platform-invariant",
                source_revision=self._platform_revision,
                trust_class=FragmentTrustClass.PLATFORM_INVARIANT,
                cache_class=FragmentCacheClass.STATIC,
                content=self._platform_invariant,
            ),
            MaterializedFragment.build(
                kind="role_profile",
                source_ref=f"role:{role.role_id}",
                source_revision=role.version,
                trust_class=FragmentTrustClass.RUNTIME_CONTROL,
                cache_class=FragmentCacheClass.STATIC,
                content=role.model_dump(mode="json"),
            ),
            MaterializedFragment.build(
                kind="task_contract",
                source_ref=f"task-contract:{contract.task_contract_id}",
                source_revision=str(contract.contract_revision),
                trust_class=FragmentTrustClass.RUNTIME_CONTROL,
                cache_class=FragmentCacheClass.TASK_STABLE,
                content=contract.model_dump(mode="json"),
            ),
            MaterializedFragment.build(
                kind="execution_context",
                source_ref=run.execution_envelope_ref,
                source_revision=resolved_execution_profile_revision,
                trust_class=FragmentTrustClass.RUNTIME_CONTROL,
                cache_class=FragmentCacheClass.TASK_STABLE,
                content={
                    "execution_envelope_ref": run.execution_envelope_ref,
                    "execution_profile": resolved_execution_profile,
                    "execution_profile_revision": resolved_execution_profile_revision,
                    "policy_context_ref": manifest.policy_context_ref,
                    "capability_envelope_ref": manifest.capability_envelope_ref,
                    "budget_ref": manifest.budget_ref,
                },
            ),
            MaterializedFragment.build(
                kind="context_reference_scope",
                source_ref=f"context:{manifest.context_id}",
                source_revision=str(manifest.context_revision),
                trust_class=FragmentTrustClass.EVIDENCE_REFERENCE,
                cache_class=FragmentCacheClass.TASK_STABLE,
                content={
                    "knowledge_revision": manifest.knowledge_revision,
                    "investigation_state_ref": manifest.investigation_state_ref,
                    "enrichment_state_refs": cast(JsonValue, manifest.enrichment_state_refs),
                    "evidence_refs": cast(JsonValue, manifest.evidence_refs),
                    "object_refs": cast(JsonValue, manifest.object_refs),
                    "relation_refs": cast(JsonValue, manifest.relation_refs),
                    "trajectory_checkpoint_ref": manifest.trajectory_checkpoint_ref,
                    "skill_selection_refs": cast(JsonValue, manifest.skill_selection_refs),
                    "experience_pattern_refs": cast(JsonValue, manifest.experience_pattern_refs),
                },
            ),
        ]

        dynamic = list(dynamic_fragments or [])
        disclosure = list(disclosure_fragments or [])
        ephemeral = list(ephemeral_fragments or [])
        _validate_fragment_classes(dynamic, FragmentCacheClass.STATE_DYNAMIC)
        _validate_fragment_classes(disclosure, FragmentCacheClass.TASK_STABLE)
        _validate_fragment_classes(ephemeral, FragmentCacheClass.EPHEMERAL)

        manifest_refs = _manifest_refs(manifest)
        allowed_disclosures = manifest_refs | set(runtime_disclosure_refs or set())
        for fragment in [*dynamic, *disclosure]:
            if fragment.source_ref not in allowed_disclosures:
                raise ValueError(
                    "ContextMaterializer cannot expand ContextManifest/runtime disclosure scope: "
                    f"{fragment.source_ref}"
                )

        fragments = _ordered_fragments([*builtins, *disclosure, *dynamic, *ephemeral])
        fragment_refs = [fragment.source_ref for fragment in fragments]
        ref_digest = _digest(sorted(set(fragment_refs)))
        ordered_ids = [fragment.fragment_id for fragment in fragments]
        resolved_percept_refs = sorted(set(percept_refs or []))
        assembly_hash = _digest(
            {
                "task_run_id": task_run_id,
                "context_id": manifest.context_id,
                "context_revision": manifest.context_revision,
                "platform_invariant_revision": self._platform_revision,
                "execution_profile_revision": resolved_execution_profile_revision,
                "policy_context_revision": manifest.policy_context_ref,
                "state_projection_revision": state_projection_revision,
                "percept_refs": resolved_percept_refs,
                "ordered_fragment_ids": ordered_ids,
                "ref_digest": ref_digest,
            }
        )
        assembly_id = str(uuid5(NAMESPACE_URL, f"secfusion:prompt-assembly:{assembly_hash}"))
        loaded_skill_refs = sorted(
            {
                fragment.source_ref
                for fragment in disclosure
                if fragment.source_ref in set(manifest.skill_selection_refs)
            }
        )
        runtime_refs = set(runtime_disclosure_refs or set())
        capability_refs = sorted(
            {
                fragment.source_ref
                for fragment in [*disclosure, *dynamic]
                if fragment.source_ref in runtime_refs
                and fragment.source_ref not in set(manifest.skill_selection_refs)
            }
        )
        cache_hints = []
        if manifest.cache_hint:
            cache_hints.append(manifest.cache_hint)
        stable_prefix = [
            fragment.fragment_id
            for fragment in fragments
            if fragment.cache_class in {FragmentCacheClass.STATIC, FragmentCacheClass.TASK_STABLE}
        ]
        if stable_prefix:
            cache_hints.append(f"prefix:{_digest(stable_prefix)[:32]}")

        return PromptAssembly(
            assembly_id=assembly_id,
            execution_id=run.execution_envelope_ref,
            task_contract_id=contract.task_contract_id,
            task_run_id=task_run_id,
            role_revision=f"{role.role_id}@{role.version}",
            context_manifest_revision=manifest.context_revision,
            platform_invariant_revision=self._platform_revision,
            execution_profile_revision=resolved_execution_profile_revision,
            policy_context_revision=manifest.policy_context_ref,
            materialized_skill_refs=loaded_skill_refs,
            materialized_capability_view_refs=capability_refs,
            state_projection_revision=state_projection_revision,
            percept_refs=resolved_percept_refs,
            materialized_fragment_refs=fragment_refs,
            materialized_ref_set_digest=ref_digest,
            ordered_fragment_ids=ordered_ids,
            cache_handle_hints=cache_hints,
            assembly_hash=assembly_hash,
            fragments=fragments,
        )


def _validate_fragment_classes(
    fragments: list[MaterializedFragment],
    expected: FragmentCacheClass,
) -> None:
    for fragment in fragments:
        if fragment.cache_class is not expected:
            raise ValueError(
                f"fragment {fragment.fragment_id} must use cache_class={expected.value}"
            )


def _manifest_refs(manifest: object) -> set[str]:
    from packages.task_runtime.contracts.models import ContextManifest

    parsed = ContextManifest.model_validate(manifest)
    refs = {
        parsed.policy_context_ref,
        parsed.capability_envelope_ref,
        parsed.budget_ref,
        *parsed.enrichment_state_refs,
        *parsed.evidence_refs,
        *parsed.object_refs,
        *parsed.relation_refs,
        *parsed.skill_selection_refs,
        *parsed.experience_pattern_refs,
    }
    if parsed.case_ref:
        refs.add(parsed.case_ref)
    if parsed.investigation_state_ref:
        refs.add(parsed.investigation_state_ref)
    if parsed.trajectory_checkpoint_ref:
        refs.add(parsed.trajectory_checkpoint_ref)
    return refs


def _ordered_fragments(fragments: list[MaterializedFragment]) -> list[MaterializedFragment]:
    return sorted(
        fragments,
        key=lambda item: (
            _CACHE_ORDER[item.cache_class],
            item.kind,
            item.source_ref,
            item.fragment_id,
        ),
    )


def _fragment_payload(fragment: MaterializedFragment) -> dict[str, JsonValue]:
    return {
        "fragment_id": fragment.fragment_id,
        "kind": fragment.kind,
        "source_ref": fragment.source_ref,
        "source_revision": fragment.source_revision,
        "disclosure_level": fragment.disclosure_level,
        "selection_reason": fragment.selection_reason,
        "trust_class": fragment.trust_class.value,
        "cache_class": fragment.cache_class.value,
        "content_hash": fragment.content_hash,
        "content": fragment.content,
    }


def _content_hash(value: JsonValue) -> str:
    return _digest(value)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
