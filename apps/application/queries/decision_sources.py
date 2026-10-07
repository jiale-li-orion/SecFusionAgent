from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.investigation.state.contracts import InvestigationState
from packages.reasoning.citation import CitationSource


async def decision_citation_sources(
    session: AsyncSession, state: InvestigationState
) -> list[CitationSource]:
    refs = {
        ref
        for group in (
            state.confirmed,
            state.tentative,
            state.conflicts,
            state.unknowns,
            state.hypotheses,
        )
        for item in group
        for ref in item.evidence_refs
        if ref.startswith("evidence:")
    }
    result = []
    for ref in sorted(refs):
        link = await session.get(EvidenceLinkModel, ref.removeprefix("evidence:"))
        if link is None:
            continue
        observation = await session.get(ObservationModel, link.observation_id)
        if observation is None:
            continue
        source = f"source:{observation.source_id}:{observation.external_object_id}"
        if observation.external_revision:
            source += f"@{observation.external_revision}"
        result.append(
            CitationSource(
                evidence_ref=ref,
                source_ref=source,
                locator=cast(dict[str, JsonValue], dict(link.locator)),
            )
        )
    return result
