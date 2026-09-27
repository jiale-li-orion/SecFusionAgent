from __future__ import annotations

import json
from hashlib import sha256
from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.investigation.runtime.contracts import InvestigationFrame
from packages.investigation.runtime.planner import PlannerCapabilityContext
from packages.runtime.capability.contracts import ExecutionClass
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.task_runtime.context.materializer import (
    FragmentCacheClass,
    FragmentTrustClass,
    MaterializedFragment,
)
from packages.task_runtime.storage.service import get_task_run


class CapabilityPlannerContextProvider:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry: CapabilityRegistry,
        policy_engine: StaticPolicyEngine,
        *,
        semantic_class_map: dict[str, list[str]] | None = None,
        healthy_refs: set[str] | None = None,
        available_execution_classes: set[ExecutionClass] | None = None,
        satisfiable_obligation_kinds: set[str] | None = None,
        execution_service: ExecutionRunService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._policy = policy_engine
        self._semantic_class_map = {
            key: sorted(set(values)) for key, values in (semantic_class_map or {}).items()
        }
        self._healthy_refs = healthy_refs
        self._available_execution_classes = available_execution_classes
        self._satisfiable_obligation_kinds = satisfiable_obligation_kinds or set()
        self._execution = execution_service or ExecutionRunService()

    async def resolve(
        self,
        *,
        task_run_id: str,
        frame: InvestigationFrame,
    ) -> PlannerCapabilityContext:
        async with self._session_factory() as session:
            run = await get_task_run(session, task_run_id)
            envelope = await self._execution.get(session, run.execution_envelope_ref)
        visible = self._registry.visible_capabilities(
            task=frame.task_contract,
            task_run_id=task_run_id,
            policy_engine=self._policy,
            capability_scope=set(envelope.capability_scope),
            healthy_refs=self._healthy_refs,
            available_execution_classes=self._available_execution_classes,
            satisfiable_obligation_kinds=self._satisfiable_obligation_kinds,
        )
        cards = [card.model_dump(mode="json") for card in visible.cards]
        view_payload: dict[str, JsonValue] = {
            "registry_revision": visible.registry_revision,
            "cards": cast(JsonValue, cards),
        }
        digest = sha256(
            json.dumps(
                view_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        view_revision = f"{visible.registry_revision}:{digest[:16]}"
        source_ref = f"capability-view:{view_revision}"
        classes: set[str] = set()
        for card in visible.cards:
            classes.add(card.capability_id)
            classes.update(self._semantic_class_map.get(card.capability_id, []))
        fragment = MaterializedFragment.build(
            kind="capability_cards",
            source_ref=source_ref,
            source_revision=view_revision,
            trust_class=FragmentTrustClass.RUNTIME_CONTROL,
            cache_class=FragmentCacheClass.STATE_DYNAMIC,
            content=view_payload,
        )
        return PlannerCapabilityContext(
            capability_view_revision=view_revision,
            execution_profile_revision=f"{envelope.execution_profile.value}@1",
            visible_capability_classes=sorted(classes),
            dynamic_fragments=[fragment],
            runtime_disclosure_refs={source_ref},
        )
