# `packages.runtime.artifacts`

`packages.runtime.artifacts` owns execution-scoped runtime blobs produced by model/tool/sandbox activity. Runtime artifacts are operational evidence of execution, not factual Evidence authority. Promotion into `Observation/EvidenceArtifact` remains an explicit higher-level operation.

## Durable identity

`RuntimeArtifactService.write()` binds an artifact to one `ExecutionRun`, producer identity, logical name, media type, trust class and content hash. The stable ref is `artifact:<artifact_id>`; the artifact ID is deterministic over execution ID + logical name + content hash. Exact replay with identical metadata returns the existing artifact. Replaying the same logical content while changing producer/media/trust metadata fails closed.

The blob store is content-addressed and lives behind `RuntimeBlobStore`. PostgreSQL stores the execution/artifact metadata and storage URI; large bytes stay in the blob store. `read()` always verifies the persisted SHA-256 before returning bytes, so a corrupted or substituted blob cannot silently pass as the recorded artifact.

## Evidence boundary

Runtime artifacts are intentionally separate from `packages.intelligence.storage.artifacts`. A sandbox stdout/model/tool result may be replayable without becoming an external-world fact. `apps.observation_promotion` is the explicit seam that reads a RuntimeArtifact and submits it through `EvidenceIngress`, where Source/Evidence authority, idempotency and raw EvidenceArtifact persistence are enforced.

## Repository boundary

The repository root may contain a local `/artifacts/` working directory, but the Python package `packages/runtime/artifacts/` must remain tracked. `.gitignore` therefore ignores only the root-level runtime directory rather than every directory named `artifacts`.

## Verification

```bash
uv run pytest packages/runtime/artifacts/tests -q
uv run pytest tests/test_runtime_artifact_bridge.py -q
uv run mypy packages/runtime/artifacts apps/runtime_artifacts.py
```
