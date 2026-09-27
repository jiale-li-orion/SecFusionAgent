from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine


class RuntimePolicyCatalog(BaseModel):
    policy_revision: str
    rules: list[RuntimePolicyRule] = Field(default_factory=list)


def load_runtime_policy(path: Path) -> StaticPolicyEngine:
    catalog = RuntimePolicyCatalog.model_validate_json(path.read_text(encoding="utf-8"))
    return StaticPolicyEngine(
        policy_revision=catalog.policy_revision,
        rules=catalog.rules,
    )
