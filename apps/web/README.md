# `apps.web`

`apps.web` is the operator/test frontend for the running SecFusionAgent application. It is deliberately separate from the project Wiki/Website: the Website explains the system, while this frontend inspects and drives the real local runtime through `apps.api`.

## Surface

FastAPI mounts this directory at `/app/`. The frontend is dependency-free static HTML/CSS/JavaScript and uses only public HTTP routes. It currently exposes:

- M1 source runtime health and executable source-category coverage;
- M2/M3 canonical vulnerability Knowledge lookup and background enrichment trigger;
- M4 Case / InvestigationState / EvidenceNeed inspection and Case creation;
- TD2 TaskRun / TaskContract / ContextManifest / TaskEvent inspection;
- policy-admitted Investigation Task creation for a selected Case;
- M6 Decision runtime execution and final/continuation output;
- M7 trajectory/snapshot coordinates already attached to a Case.

The frontend has no direct database access and owns no business state. Mutations call `/api/v1/workbench/*`, whose server-side composition still passes through Case/State services, Task admission/Policy, the production enrichment worker path, or DecisionRuntime as appropriate.

## Run

With PostgreSQL/Redis dependencies available:

```bash
uv run uvicorn apps.api.main:app --reload
```

Open `http://127.0.0.1:8000/app/`.

Workbench mutations are intended for local testing and require `SECFUSION_ENVIRONMENT=dev|test` plus `SECFUSION_API_WORKBENCH_ENABLED=true`. The application does not expose this as a production admin authorization mechanism.
