from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.enrichment.runtime.tasks import build_vulnerability_enrichment_contract
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.task_runtime.contracts.models import TaskContract, TaskIntent, TaskKind


class EnrichmentAdmissionBinding(BaseModel):
    target_object_id: str
    cve_id: str
    required_dimensions: list[EnrichmentDimension] = Field(min_length=1)
    refresh_dimensions: list[EnrichmentDimension] = Field(default_factory=list)
    trigger_ref: str | None = None

    @model_validator(mode="after")
    def validate_binding(self) -> EnrichmentAdmissionBinding:
        if not self.target_object_id.strip() or not self.cve_id.strip():
            raise ValueError("Enrichment admission object/CVE identity cannot be empty")
        return self


class EnrichmentTaskContractCompiler:
    task_kind = TaskKind.ENRICHMENT
    compiler_revision = "enrichment-admission-v1"

    def compile(
        self,
        intent: TaskIntent,
        *,
        task_contract_id: str,
        contract_revision: int,
        principal: str,
        on_behalf_of: str | None,
        policy_revision: str,
        binding_context: dict[str, JsonValue],
    ) -> TaskContract:
        binding = EnrichmentAdmissionBinding.model_validate(binding_context)
        allowed_targets = {
            binding.target_object_id,
            f"object:{binding.target_object_id}",
            binding.cve_id.upper(),
            f"cve:{binding.cve_id.upper()}",
        }
        unexpected = [item for item in intent.candidate_targets if item not in allowed_targets]
        if unexpected:
            raise ValueError(f"Enrichment admission target is not bound: {unexpected[0]}")
        contract = build_vulnerability_enrichment_contract(
            task_contract_id=task_contract_id,
            principal=principal,
            target_object_id=binding.target_object_id,
            cve_id=binding.cve_id,
            required_dimensions=binding.required_dimensions,
            refresh_dimensions=binding.refresh_dimensions,
            policy_revision=policy_revision,
            contract_revision=contract_revision,
            on_behalf_of=on_behalf_of,
        )
        if binding.trigger_ref is not None:
            contract.target_resources.append(f"processing-run:{binding.trigger_ref}")
        return contract
