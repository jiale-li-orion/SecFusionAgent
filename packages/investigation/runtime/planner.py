from __future__ import annotations

from hashlib import sha256
from typing import Protocol, cast

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.investigation.perception.contracts import Percept
from packages.investigation.runtime.context import (
    materialize_investigation_context_fragments,
    materialize_investigation_prompt,
)
from packages.investigation.runtime.contracts import (
    DelegationAction,
    InvestigationAction,
    InvestigationFrame,
    InvestigationPlannerDecision,
    PerceptionAction,
    StatePatchAction,
    StopAction,
    WaitAction,
)
from packages.investigation.skills.contracts import SkillDisclosureLevel
from packages.investigation.skills.materialize import materialize_skill_selection
from packages.investigation.skills.resolver import SkillResolutionContext, SkillResolver
from packages.investigation.skills.service import SkillStore
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.context.contracts import ContextRefresh
from packages.task_runtime.context.materializer import (
    ContextMaterializer,
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
    PromptAssembly,
)
from packages.task_runtime.context.service import refresh_context
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    get_task_context,
    update_task_context,
)


class PlannerCapabilityContext(BaseModel):
    capability_view_revision: str = "capability-view:none"
    execution_profile_revision: str | None = None
    visible_capability_classes: list[str] = Field(default_factory=list)
    disclosure_fragments: list[MaterializedFragment] = Field(default_factory=list)
    dynamic_fragments: list[MaterializedFragment] = Field(default_factory=list)
    runtime_disclosure_refs: set[str] = Field(default_factory=set)


class PlannerCapabilityContextProvider(Protocol):
    async def resolve(
        self,
        *,
        task_run_id: str,
        frame: InvestigationFrame,
    ) -> PlannerCapabilityContext: ...


class EmptyPlannerCapabilityContextProvider:
    async def resolve(
        self,
        *,
        task_run_id: str,
        frame: InvestigationFrame,
    ) -> PlannerCapabilityContext:
        del task_run_id, frame
        return PlannerCapabilityContext()


class PromptAssemblyRecorder(Protocol):
    async def persist(
        self,
        session: AsyncSession,
        *,
        assembly: PromptAssembly,
        context_manifest_ref: str,
    ) -> None: ...


class NullPromptAssemblyRecorder:
    async def persist(
        self,
        session: AsyncSession,
        *,
        assembly: PromptAssembly,
        context_manifest_ref: str,
    ) -> None:
        del session, assembly, context_manifest_ref


class SourceInvestigationPlannerDecision(BaseModel):
    """Non-vulnerability objects use local perception and the existing M4 state gate."""

    action: PerceptionAction | StatePatchAction | WaitAction | StopAction = Field(
        discriminator="kind"
    )
    decision_note: str | None = None


_SOURCE_EVIDENCE_GUIDANCE = MaterializedFragment.build(
    kind="source_investigation_guidance",
    source_ref="runtime-guidance:source-investigation-v2",
    source_revision="source-investigation-v2",
    trust_class=FragmentTrustClass.RUNTIME_CONTROL,
    cache_class=FragmentCacheClass.TASK_STABLE,
    content={
        "instruction": (
            "For a source or document investigation, persist each clearly supported "
            "subfinding with a StatePatch as soon as its citable passage is available. "
            "Do not wait until every target or comparison dimension is covered before "
            "recording a supported fact. Leave resolves_need_id empty until the whole "
            "EvidenceNeed is satisfied. Use only evidence_refs visible in the Percepts "
            "and bound target object IDs. A source's silence is not proof of a negative "
            "fact. After a focused search returns no new evidence, report the remaining "
            "gap with WAIT or STOP; do not repeat the same inspection."
        )
    },
)


class ModelInvestigationPlanner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: ModelProvider,
        *,
        materializer: ContextMaterializer,
        skill_resolver: SkillResolver | None = None,
        skill_store: SkillStore | None = None,
        capability_context_provider: PlannerCapabilityContextProvider | None = None,
        prompt_assembly_recorder: PromptAssemblyRecorder | None = None,
        stream_name: str = "secfusion:task-events",
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._materializer = materializer
        self._skill_store = skill_store or SkillStore()
        self._skill_resolver = skill_resolver or SkillResolver(self._skill_store)
        self._capability_context_provider = (
            capability_context_provider or EmptyPlannerCapabilityContextProvider()
        )
        self._prompt_assembly_recorder = prompt_assembly_recorder or NullPromptAssemblyRecorder()
        self._stream_name = stream_name

    async def next_action(self, frame: InvestigationFrame) -> InvestigationAction:
        capability_context = await self._capability_context_provider.resolve(
            task_run_id=frame.task_run_id,
            frame=frame,
        )
        async with self._session_factory() as session, session.begin():
            manifest = await get_task_context(session, frame.task_run_id)
            context_fragments = await materialize_investigation_context_fragments(
                session,
                manifest,
            )
            object_ref_aliases = _visible_object_ref_aliases(context_fragments)
            object_types = _object_types(context_fragments)
            source_task = "Vulnerability" not in object_types
            role = canonical_roles()["InvestigationRole"]
            selection = await self._skill_resolver.resolve(
                session,
                task=frame.task_contract,
                role=role,
                context=SkillResolutionContext(
                    task_run_id=frame.task_run_id,
                    object_types=object_types,
                    visible_capability_classes=capability_context.visible_capability_classes,
                    available_inputs=[
                        "task_contract",
                        "investigation_state",
                        *(["last_percept"] if frame.last_percept is not None else []),
                    ],
                    state_signature=f"case:{frame.state.case_id}@{frame.state.case_revision}",
                    capability_view_revision=capability_context.capability_view_revision,
                ),
                evidence_need=frame.selected_need,
            )
            if selection.selected_skill_ref is not None and selection.selected_skill_ref not in set(
                manifest.skill_selection_refs
            ):
                manifest = refresh_context(
                    manifest,
                    ContextRefresh(
                        context_revision=manifest.context_revision + 1,
                        knowledge_revision=manifest.knowledge_revision,
                        investigation_state_ref=manifest.investigation_state_ref,
                        add_skill_selection_refs=[selection.selected_skill_ref],
                        cache_hint=None,
                    ),
                )
                await update_task_context(
                    session,
                    run_id=frame.task_run_id,
                    manifest=manifest,
                    stream_name=self._stream_name,
                    producer="InvestigationRole:SkillResolver",
                )

            skill_fragments = await materialize_skill_selection(
                session,
                selection=selection,
                disclosure_level=SkillDisclosureLevel.PROCEDURE,
                store=self._skill_store,
            )
            ephemeral = [
                fragment
                for percept in (frame.recent_percepts or [frame.last_percept])
                if percept is not None
                for fragment in _percept_fragments(percept)
            ]
            assembly = await materialize_investigation_prompt(
                session,
                task_run_id=frame.task_run_id,
                materializer=self._materializer,
                disclosure_fragments=[
                    *capability_context.disclosure_fragments,
                    *skill_fragments,
                    *([_SOURCE_EVIDENCE_GUIDANCE] if source_task else []),
                ],
                additional_dynamic_fragments=capability_context.dynamic_fragments,
                ephemeral_fragments=ephemeral,
                runtime_disclosure_refs=(
                    capability_context.runtime_disclosure_refs
                    | ({_SOURCE_EVIDENCE_GUIDANCE.source_ref} if source_task else set())
                ),
                percept_refs=[item.source_ref for item in ephemeral],
                execution_profile_revision=capability_context.execution_profile_revision,
            )
            await self._prompt_assembly_recorder.persist(
                session,
                assembly=assembly,
                context_manifest_ref=f"context:{manifest.context_id}",
            )

        prompt_revision = (
            "investigation-model-v2-source" if source_task else "investigation-model-v1"
        )
        request = assembly.to_model_request()
        request = request.model_copy(
            update={
                "metadata": {
                    **request.metadata,
                    "model_purpose": "m5.investigation_plan",
                    "prompt_revision": prompt_revision,
                    "request_owner_ref": f"task-run:{frame.task_run_id}",
                    "execution_id": assembly.execution_id,
                    "task_run_id": assembly.task_run_id,
                    "case_id": frame.state.case_id,
                    "prompt_assembly_id": assembly.assembly_id,
                    "budget_ref": manifest.budget_ref,
                    "planner": prompt_revision,
                    "iteration": frame.iteration,
                    "selected_need_id": (
                        frame.selected_need.need_id if frame.selected_need is not None else None
                    ),
                    "model_payload_persistence": "redacted_runtime_artifact",
                    "model_provider": f"{self._provider.name}@{self._provider.version}",
                }
            }
        )
        response_model = (
            InvestigationPlannerDecision
            if "Vulnerability" in object_types
            else SourceInvestigationPlannerDecision
        )
        decision = cast(
            InvestigationPlannerDecision | SourceInvestigationPlannerDecision,
            await self._provider.generate_structured(request, response_model),
        )
        return _normalize_action(
            decision.action,
            frame=frame,
            assembly_hash=assembly.assembly_hash,
            provider_ref=f"{self._provider.name}@{self._provider.version}",
            budget_ref=manifest.budget_ref,
            object_ref_aliases=object_ref_aliases,
        )


def _object_types(fragments: list[MaterializedFragment]) -> list[str]:
    result: set[str] = set()
    for fragment in fragments:
        if fragment.kind != "knowledge_object" or not isinstance(fragment.content, dict):
            continue
        object_type = fragment.content.get("object_type")
        if isinstance(object_type, str) and object_type:
            result.add(object_type)
    return sorted(result)


def _percept_fragments(percept: Percept | None) -> list[MaterializedFragment]:
    if percept is None:
        return []
    source_ref = (
        percept.percept_id
        if percept.percept_id.startswith("percept:")
        else f"percept:{percept.percept_id}"
    )
    return [
        MaterializedFragment.build(
            kind="percept",
            source_ref=source_ref,
            source_revision=percept.request_id,
            trust_class=FragmentTrustClass.UNTRUSTED_EXTERNAL,
            cache_class=FragmentCacheClass.EPHEMERAL,
            content=cast(JsonValue, percept.model_dump(mode="json")),
        )
    ]


def _normalize_action(
    action: InvestigationAction,
    *,
    frame: InvestigationFrame,
    assembly_hash: str,
    provider_ref: str,
    budget_ref: str,
    object_ref_aliases: dict[str, str] | None = None,
) -> InvestigationAction:
    if isinstance(action, PerceptionAction):
        request_id = f"perception:{frame.task_run_id}:{frame.iteration}:{assembly_hash[:16]}"
        request = action.request.model_copy(
            update={
                "request_id": request_id,
                "case_id": frame.state.case_id,
                "need_id": frame.selected_need.need_id if frame.selected_need else None,
                "budget_ref": budget_ref,
            }
        )
        return PerceptionAction(request=request)
    if isinstance(action, StatePatchAction):
        patch_id = f"patch:{frame.task_run_id}:{frame.iteration}:{assembly_hash[:16]}"
        operations = [
            operation.model_copy(
                update={
                    "target_ref": _normalize_patch_target_ref(
                        operation.target_ref,
                        frame=frame,
                        object_ref_aliases=object_ref_aliases or {},
                    )
                }
            )
            for operation in action.patch.operations
        ]
        patch = action.patch.model_copy(
            update={
                "patch_id": patch_id,
                "case_id": frame.state.case_id,
                "base_case_revision": frame.state.case_revision,
                "operations": operations,
                "producer": f"InvestigationRole:model:{provider_ref}",
                "model_prompt_revision": assembly_hash,
            }
        )
        return StatePatchAction(patch=patch)
    if isinstance(action, DelegationAction):
        identity = sha256(
            (
                f"{frame.task_run_id}|"
                f"{action.request.target_object_id}|{action.request.cve_id}|"
                f"{','.join(sorted(action.request.required_dimensions))}"
            ).encode()
        ).hexdigest()[:24]
        return DelegationAction(
            request=action.request.model_copy(update={"delegation_id": f"delegation:{identity}"})
        )
    return action


def _normalize_patch_target_ref(
    target_ref: str | None,
    *,
    frame: InvestigationFrame,
    object_ref_aliases: dict[str, str] | None = None,
) -> str | None:
    if target_ref is None:
        return None
    if target_ref in set(frame.state.targets):
        return f"object:{target_ref}"
    alias = (object_ref_aliases or {}).get(target_ref)
    if alias is not None:
        return alias
    return target_ref


def _visible_object_ref_aliases(fragments: list[MaterializedFragment]) -> dict[str, str]:
    """Map model-visible object identities to the stable M4 target-ref form.

    Knowledge-object fragments can embed relation targets as full object views. The model may
    therefore emit a canonical key (for example ``software-version:npm:knowns:0.30.0``) even
    though the M4 write gate intentionally accepts only stable ``object:<uuid>`` refs. Resolve
    aliases only from the already-materialized Evidence World that was shown to the model; do not
    perform a broader database lookup or weaken M4 validation.
    """

    aliases: dict[str, str] = {}
    for fragment in fragments:
        _collect_object_ref_aliases(fragment.content, aliases)
    return aliases


def _collect_object_ref_aliases(value: JsonValue, aliases: dict[str, str]) -> None:
    if isinstance(value, dict):
        object_id = value.get("object_id")
        canonical_key = value.get("canonical_key")
        if isinstance(object_id, str) and object_id:
            stable_ref = f"object:{object_id}"
            aliases.setdefault(object_id, stable_ref)
            aliases.setdefault(stable_ref, stable_ref)
            if isinstance(canonical_key, str) and canonical_key:
                aliases.setdefault(canonical_key, stable_ref)
        for child in value.values():
            _collect_object_ref_aliases(child, aliases)
        return
    if isinstance(value, list):
        for child in value:
            _collect_object_ref_aliases(child, aliases)
