from __future__ import annotations

import re

from pydantic import JsonValue

from packages.task_runtime.contracts.models import TaskIntent, TaskKind

_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_GHSA = re.compile(r"\bGHSA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b", re.IGNORECASE)
_RESOURCE_REF = re.compile(
    r"\b(?:case|object|incident|repo|release|commit|cve|ghsa):[A-Za-z0-9._/@:+-]+\b",
    re.IGNORECASE,
)


class TaskIntentParser:
    """Deterministic L0 intent parsing only.

    The parser extracts stable identifiers and explicit resource references. It
    deliberately does not infer TaskKind from open-ended natural language;
    ambiguous classification remains outside this deterministic boundary.
    """

    def parse(
        self,
        *,
        raw_request: str | None = None,
        trigger_ref: str | None = None,
        candidate_task_kind: TaskKind | None = None,
        candidate_targets: list[str] | None = None,
        temporal_expression: str | None = None,
        requested_output: dict[str, JsonValue] | None = None,
        requested_actions: list[str] | None = None,
        context_refs: list[str] | None = None,
    ) -> TaskIntent:
        text = raw_request or ""
        identifiers: list[str] = []
        identifiers.extend(item.upper() for item in _CVE.findall(text))
        identifiers.extend(item.upper() for item in _GHSA.findall(text))
        resource_refs = [item for item in _RESOURCE_REF.findall(text)]
        identifiers.extend(resource_refs)

        explicit_targets = list(candidate_targets or [])
        for ref in resource_refs:
            if ref.lower().startswith(("case:", "object:", "incident:")):
                explicit_targets.append(ref)

        return TaskIntent(
            raw_request=raw_request,
            trigger_ref=trigger_ref,
            parsed_identifiers=_unique(identifiers),
            candidate_task_kind=candidate_task_kind,
            candidate_targets=_unique(explicit_targets),
            temporal_expression=temporal_expression,
            requested_output=dict(requested_output or {}),
            requested_actions=_unique(list(requested_actions or [])),
            context_refs=_unique(list(context_refs or [])),
        )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item.strip()))
