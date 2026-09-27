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

Skill storage, deterministic resolution, progressive disclosure and candidate seeds are implemented. Experience compression and `SkillPatchCandidate` proposal are implemented under `packages.investigation.experience`; replay/regression and activation are implemented by `packages.evaluation.skill_promotion`. This package intentionally does **not** own promotion authority.

The built-in seed Skills still remain `candidate` because the existence of the M7 gate does not itself produce validation evidence. A Skill becomes online-selectable only after a concrete replay suite writes the required validation/promotion reference and its status moves to `validated/active`.

## Design → implementation map

TD2 的渐进披露在代码里对应 `SkillStore.search_manifests → get_procedure → get_step → get_provenance`；`SkillResolver.resolve` 只在当前 Task/EvidenceNeed/object/capability 条件内做确定性选择。Experience-derived patch 由 `ExperienceCompressor.propose_patch` 生成新 immutable version，随后交给 `packages.evaluation.SkillPromotionGate`；Skill package 本身没有“自动学习成功就激活”的捷径。

## Verification

```bash
uv run pytest packages/investigation/skills -q
uv run ruff check packages/investigation/skills
uv run mypy packages/investigation/skills
```
