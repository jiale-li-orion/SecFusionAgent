# `packages.investigation.skills`

This package owns M5 investigation Skill versions and progressive model disclosure. It does not own Task scheduling, factual authority, capability authorization or physical tool bindings.

## Durable contract

`SkillManifest` is the discovery surface. `SkillProcedure` contains semantic investigation steps, evidence expectations, failure guards, fallbacks and stop conditions. `SkillStepFragment` discloses the currently relevant step. `SkillProvenance` records origin and validation/promotion history and is normally excluded from online model instructions.

`SkillStore` persists immutable `(skill_id, version)` content in `skill_versions` and exposes `search_manifests / get_procedure / get_step / get_provenance`. A procedure containing concrete URLs, shell commands or native tool hints is rejected; those choices belong to Capability Binding.

## Resolution and disclosure

`SkillResolver` filters by Role namespace, validation status, Task kind, EvidenceNeed signature, object types, required inputs, visible capability classes and applicability conditions, then applies deterministic ranking. Default search includes `validated/active` only.

`materialize_skill_selection` implements `manifest → procedure → step → provenance` disclosure. Manifest/procedure are task-stable procedural fragments, step is state-dynamic, and provenance is ephemeral `procedural_provenance` data that cannot become a system instruction.

The built-in five TD2 seed skills are `candidate` until M7 replay/regression produces a validation reference. `InvestigationRole.seed_skill_refs` therefore remains empty at the current Role revision.

## Current boundary

Skill storage, deterministic resolution, progressive disclosure and candidate seeds are implemented. Automatic Experience compression, `SkillPatchCandidate`, regression replay and promotion are intentionally absent until M7; candidate presence must not be described as learned/adaptive Skill behavior.

## Verification

```bash
uv run pytest packages/investigation/skills -q
uv run ruff check packages/investigation/skills
uv run mypy packages/investigation/skills
```
