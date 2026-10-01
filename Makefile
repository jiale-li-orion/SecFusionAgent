.PHONY: sync lint format typecheck test check site-check site-status dev-up dev-runtime-up dev-runtime-down runtime-status runtime-config-check data-plane-up data-plane-down data-plane-status data-plane-logs dev-down migrate sync-sources sync-skills worker worker-collection scheduler task-event-dispatcher task-event-scheduler probe-nvd promote-hot product-check model-provider-probe qa-live qa-live-preflight benchmark-query m1-doc m1-render-doc m1-doc-check qa-preflight qa-preflight-doc-check investigation-readiness investigation-readiness-doc-check fault-recovery fault-recovery-doc-check competition-report competition-render-doc competition-doc-check readme-evidence readme-evidence-check evidence-doc evidence-doc-check

WIKI_PATH ?= ../SecFusionAgent.wiki
SITE_STATUS_OUTPUT ?= $(WIKI_PATH)/site/project-status.json
M1_SUITE_ID ?= m1-monitoring-current
M1_STATUS_JSON ?= benchmarks/m1/current.json
M1_STATUS_MD ?= benchmarks/m1/current.md
M1_STATUS_README ?= benchmarks/m1/README.md
M1_DELIVERY_GRACE_SECONDS ?= 21600
QA_PRODUCT_PREFLIGHT_JSON ?= benchmarks/qa/current-product-preflight.json
QA_SESSION_PREFLIGHT_JSON ?= benchmarks/qa/current-session-preflight.json
QA_PREFLIGHT_MD ?= benchmarks/qa/current-preflight.md
INVESTIGATION_READINESS_JSON ?= benchmarks/investigation/current-readiness.json
INVESTIGATION_READINESS_MD ?= benchmarks/investigation/current-readiness.md
FAULT_RECOVERY_JSON ?= benchmarks/fault-recovery/current.json
FAULT_RECOVERY_MD ?= benchmarks/fault-recovery/current.md
COMPETITION_RUN_SET ?= benchmarks/competition/current-run-set.json
COMPETITION_STATUS_JSON ?= benchmarks/competition/current.json
COMPETITION_STATUS_MD ?= benchmarks/competition/current.md

sync:
	uv sync --dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy apps packages scripts

test:
	uv run pytest

check: lint typecheck test

product-check:
	uv run pytest -q \
		apps/application/tests \
		apps/api/tests/test_product_investigations.py \
		apps/api/tests/test_product_questions.py \
		apps/api/tests/test_product_edge.py \
		packages/reasoning/tests \
		tests/test_decision_runtime.py

site-check:
	python3 scripts/validate_site.py --site $(WIKI_PATH)/site

site-status:
	python3 scripts/build_site_status.py --repo . --wiki $(WIKI_PATH) --output $(SITE_STATUS_OUTPUT)

m1-doc:
	@test -n "$(M1_WINDOW_START)" || (echo "M1_WINDOW_START is required" >&2; exit 2)
	@test -n "$(M1_WINDOW_END)" || (echo "M1_WINDOW_END is required" >&2; exit 2)
	@test -n "$(M1_SUITE_REVISION)" || (echo "M1_SUITE_REVISION is required" >&2; exit 2)
	uv run python scripts/run_m1_benchmark.py \
		--window-start "$(M1_WINDOW_START)" \
		--window-end "$(M1_WINDOW_END)" \
		--suite-id "$(M1_SUITE_ID)" \
		--suite-revision "$(M1_SUITE_REVISION)" \
		$(if $(M1_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(M1_DEPLOYMENT_REVISION_ID)") \
		$(if $(M1_EXPECTED_EVENTS_MANIFEST),--expected-events-manifest "$(M1_EXPECTED_EVENTS_MANIFEST)") \
		--delivery-grace-seconds "$(M1_DELIVERY_GRACE_SECONDS)" \
		--output "$(M1_STATUS_JSON)" \
		--markdown-output "$(M1_STATUS_MD)" \
		--readme-status "$(M1_STATUS_README)"

m1-render-doc:
	@test -f "$(M1_STATUS_JSON)" || (echo "$(M1_STATUS_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_m1_status.py "$(M1_STATUS_JSON)" \
		--markdown-output "$(M1_STATUS_MD)" \
		--readme-status "$(M1_STATUS_README)"

m1-doc-check:
	@test -f "$(M1_STATUS_JSON)" || (echo "$(M1_STATUS_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_m1_status.py "$(M1_STATUS_JSON)" \
		--markdown-output "$(M1_STATUS_MD)" \
		--readme-status "$(M1_STATUS_README)" \
		--check

model-provider-probe:
	uv run python -m scripts.probe_model_provider

qa-live:
	uv run python -m scripts.run_live_qa_batch

qa-live-preflight:
	uv run python -m scripts.validate_qa_manifest --rebase-current benchmarks/qa/real-product-v1.candidate.json
	uv run python -m scripts.validate_qa_manifest --rebase-current benchmarks/qa/real-session-v1.candidate.json

benchmark-query:
	uv run python -m scripts.query_benchmark_evidence $(if $(METRIC),--metric "$(METRIC)")

fault-recovery:
	@test -n "$(FAULT_RECOVERY_SUITE_REVISION)" || (echo "FAULT_RECOVERY_SUITE_REVISION is required" >&2; exit 2)
	uv run python scripts/run_fault_recovery_benchmark.py \
		--suite-revision "$(FAULT_RECOVERY_SUITE_REVISION)" \
		$(if $(FAULT_RECOVERY_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(FAULT_RECOVERY_DEPLOYMENT_REVISION_ID)") \
		--output "$(FAULT_RECOVERY_JSON)"
	uv run python scripts/render_fault_recovery_status.py \
		"$(FAULT_RECOVERY_JSON)" \
		--markdown-output "$(FAULT_RECOVERY_MD)"

fault-recovery-doc-check:
	@test -f "$(FAULT_RECOVERY_JSON)" || (echo "$(FAULT_RECOVERY_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_fault_recovery_status.py \
		"$(FAULT_RECOVERY_JSON)" \
		--markdown-output "$(FAULT_RECOVERY_MD)" \
		--check

investigation-readiness:
	uv run python scripts/check_investigation_readiness.py \
		--output "$(INVESTIGATION_READINESS_JSON)"
	uv run python scripts/render_investigation_readiness.py \
		"$(INVESTIGATION_READINESS_JSON)" \
		--markdown-output "$(INVESTIGATION_READINESS_MD)"

investigation-readiness-doc-check:
	@test -f "$(INVESTIGATION_READINESS_JSON)" || (echo "$(INVESTIGATION_READINESS_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_investigation_readiness.py \
		"$(INVESTIGATION_READINESS_JSON)" \
		--markdown-output "$(INVESTIGATION_READINESS_MD)" \
		--check

qa-preflight:
	uv run python -m scripts.validate_qa_manifest \
		benchmarks/qa/real-product-v1.candidate.json \
		--output "$(QA_PRODUCT_PREFLIGHT_JSON)"
	uv run python -m scripts.validate_qa_manifest \
		benchmarks/qa/real-session-v1.candidate.json \
		--output "$(QA_SESSION_PREFLIGHT_JSON)"
	uv run python scripts/render_qa_preflight_status.py \
		--product "$(QA_PRODUCT_PREFLIGHT_JSON)" \
		--session "$(QA_SESSION_PREFLIGHT_JSON)" \
		--markdown-output "$(QA_PREFLIGHT_MD)"

qa-preflight-doc-check:
	@test -f "$(QA_PRODUCT_PREFLIGHT_JSON)" || (echo "$(QA_PRODUCT_PREFLIGHT_JSON) does not exist" >&2; exit 2)
	@test -f "$(QA_SESSION_PREFLIGHT_JSON)" || (echo "$(QA_SESSION_PREFLIGHT_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_qa_preflight_status.py \
		--product "$(QA_PRODUCT_PREFLIGHT_JSON)" \
		--session "$(QA_SESSION_PREFLIGHT_JSON)" \
		--markdown-output "$(QA_PREFLIGHT_MD)" \
		--check

competition-report:
	@test -f "$(COMPETITION_RUN_SET)" || (echo "$(COMPETITION_RUN_SET) does not exist" >&2; exit 2)
	uv run python scripts/export_competition_report.py \
		--run-set-manifest "$(COMPETITION_RUN_SET)" \
		--json-output "$(COMPETITION_STATUS_JSON)" \
		--markdown-output "$(COMPETITION_STATUS_MD)"

competition-render-doc:
	@test -f "$(COMPETITION_STATUS_JSON)" || (echo "$(COMPETITION_STATUS_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_competition_status.py "$(COMPETITION_STATUS_JSON)" \
		--markdown-output "$(COMPETITION_STATUS_MD)"

competition-doc-check:
	@test -f "$(COMPETITION_STATUS_JSON)" || (echo "$(COMPETITION_STATUS_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_competition_status.py "$(COMPETITION_STATUS_JSON)" \
		--markdown-output "$(COMPETITION_STATUS_MD)" \
		--check

readme-evidence:
	uv run python scripts/render_readme_evidence.py

readme-evidence-check:
	uv run python scripts/render_readme_evidence.py --check

evidence-doc: m1-render-doc qa-preflight investigation-readiness competition-render-doc readme-evidence

evidence-doc-check: m1-doc-check qa-preflight-doc-check investigation-readiness-doc-check fault-recovery-doc-check competition-doc-check readme-evidence-check

dev-up:
	docker compose -f deploy/docker-compose.yml up -d --wait postgres redis-broker redis-cache redis-task-bus localstack-s3

runtime-config-check:
	docker compose -f deploy/docker-compose.yml --profile runtime config --quiet

dev-runtime-up: dev-up migrate sync-sources sync-skills runtime-config-check
	docker compose -f deploy/docker-compose.yml --profile runtime up -d --build scheduler worker-collection worker

# Long-lived M1-M3 data plane. This intentionally does not configure or require a
# model provider; with SECFUSION_MODEL_* unset, document indexing stays lexical
# and Investigation/QA model calls are not started by this target.
data-plane-up: dev-runtime-up

data-plane-down: dev-runtime-down

data-plane-status:
	docker compose -f deploy/docker-compose.yml --profile runtime ps postgres redis-broker redis-cache redis-task-bus localstack-s3 scheduler worker-collection worker
	uv run python -m scripts.data_plane_status

data-plane-logs:
	docker compose -f deploy/docker-compose.yml --profile runtime logs --tail=200 scheduler worker-collection worker

dev-runtime-down:
	docker compose -f deploy/docker-compose.yml --profile runtime stop scheduler worker-collection worker

runtime-status:
	docker compose -f deploy/docker-compose.yml --profile runtime ps scheduler worker-collection worker

.PHONY: dev-up-core
dev-up-core:
	docker compose -f deploy/docker-compose.yml up -d --wait postgres redis-broker redis-cache redis-task-bus

.PHONY: integration-core
integration-core: dev-up-core migrate sync-sources sync-skills
	SECFUSION_RUN_INTEGRATION=1 uv run pytest -m integration \
		tests/integration/test_core_infrastructure.py \
		tests/integration/test_m3_handoff.py \
		tests/integration/test_task_runtime_protocol.py \
		tests/integration/test_enrichment_task_runtime.py \
		tests/integration/test_investigation_runtime.py \
		tests/integration/test_runtime_control_plane.py

dev-down:
	docker compose -f deploy/docker-compose.yml --profile runtime down

migrate:
	uv run alembic upgrade head

sync-sources:
	uv run python -m scripts.sync_sources

sync-skills:
	uv run python -m scripts.sync_skills

worker:
	uv run celery -A apps.worker.celery_app:celery_app worker -l INFO -Q collection,enrichment,investigation,indexing

worker-collection:
	uv run celery -A apps.worker.celery_app:celery_app worker -l INFO -Q collection

scheduler:
	uv run python -m apps.worker.scheduler

task-event-dispatcher:
	uv run python -m apps.worker.task_event_dispatcher

task-event-scheduler:
	uv run python -m apps.worker.task_event_scheduler

probe-nvd:
	uv run python -m scripts.probe_nvd_hot --limit 20

promote-hot:
	uv run python -m scripts.promote_hot_bug $(CVE)

.PHONY: probe-live-sources
probe-live-sources:
	uv run python -m scripts.probe_live_sources

.PHONY: dev-up-s3-test
dev-up-s3-test:
	docker compose -f deploy/docker-compose.yml up -d --wait localstack-s3

.PHONY: integration-object-store
integration-object-store: dev-up-s3-test
	SECFUSION_RUN_INTEGRATION=1 SECFUSION_S3_ENDPOINT_URL=http://localhost:4566 uv run pytest -m integration tests/integration/test_object_storage.py

.PHONY: integration-all
integration-all: integration-core integration-object-store

.PHONY: verify-m3
verify-m3: check source-inventory-check integration-all

.PHONY: source-inventory-check
source-inventory-check:
	uv run python -m scripts.check_source_inventory $(WIKI_PATH)/site/data/source-catalog.zh.js
	uv run python -m scripts.check_source_catalog_pair \
		$(WIKI_PATH)/site/data/source-catalog.zh.js \
		$(WIKI_PATH)/site/data/source-catalog.en.js

.PHONY: verify-data-sources
verify-data-sources: source-inventory-check
	uv run pytest packages/sources/tests -q

.PHONY: evaluation-check
evaluation-check:
	uv run pytest -q packages/evaluation packages/runtime/model/tests \
		tests/test_architecture_dependencies.py \
		tests/test_evaluation_runtime.py \
		tests/test_qa_benchmark_manifest.py \
		tests/test_qa_adjudication.py
