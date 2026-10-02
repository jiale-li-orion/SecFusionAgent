.PHONY: sync lint format typecheck test check site-check site-status dev-up dev-runtime-up dev-runtime-down runtime-status runtime-config-check data-plane-up data-plane-down data-plane-status data-plane-logs data-plane-metrics data-plane-metrics-render data-plane-metrics-check data-plane-site data-plane-site-check dev-down migrate sync-sources sync-skills worker worker-collection scheduler task-event-dispatcher task-event-scheduler probe-nvd promote-hot product-check model-provider-probe qa-live qa-live-preflight benchmark-query m1-doc m1-render-doc m1-doc-check m2-diagnostics m2-diagnostics-render m2-diagnostics-check qa-preflight qa-preflight-doc-check investigation-readiness investigation-readiness-doc-check investigation-probe evaluation-infra-status evaluation-infra-render evaluation-infra-check retrieval-benchmark retrieval-benchmark-render retrieval-benchmark-check security-benchmark security-benchmark-render security-benchmark-check security-adversarial-benchmark security-adversarial-render security-adversarial-check fault-recovery fault-recovery-doc-check competition-report competition-render-doc competition-doc-check readme-evidence readme-evidence-check evidence-doc evidence-doc-check

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
INVESTIGATION_PROBE_DEADLINE_SECONDS ?= 300
INVESTIGATION_PROBE_AGENT_TURNS ?= 8
INVESTIGATION_PROBE_TOOL_CALLS ?= 12
FAULT_RECOVERY_JSON ?= benchmarks/fault-recovery/current.json
FAULT_RECOVERY_MD ?= benchmarks/fault-recovery/current.md
EVALUATION_INFRA_JSON ?= benchmarks/evaluation-infra/current.json
EVALUATION_INFRA_MD ?= benchmarks/evaluation-infra/current.md
RETRIEVAL_BENCHMARK_JSON ?= benchmarks/retrieval/current.json
RETRIEVAL_BENCHMARK_MD ?= benchmarks/retrieval/current.md
SECURITY_BENCHMARK_JSON ?= benchmarks/security/current.json
SECURITY_BENCHMARK_MD ?= benchmarks/security/current.md
SECURITY_ADVERSARIAL_JSON ?= benchmarks/security/adversarial-current.json
SECURITY_ADVERSARIAL_MD ?= benchmarks/security/adversarial-current.md
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

site-check: data-plane-site-check
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
	uv run python -m scripts.query_benchmark_evidence \
		$(if $(REPORT),--report "$(REPORT)") \
		$(if $(RUN_ID),--run-id "$(RUN_ID)") \
		$(if $(CASE_RUN_ID),--case-run-id "$(CASE_RUN_ID)") \
		$(if $(METRIC),--metric "$(METRIC)") \
		$(if $(REQUIRE_CLOSED),--require-closed)

m2-diagnostics:
	@test -n "$(M2_DIAGNOSTICS_SUITE_REVISION)" || (echo "M2_DIAGNOSTICS_SUITE_REVISION is required" >&2; exit 2)
	uv run python -m scripts.run_m2_diagnostics_benchmark \
		--suite-revision "$(M2_DIAGNOSTICS_SUITE_REVISION)" \
		$(if $(M2_DIAGNOSTICS_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(M2_DIAGNOSTICS_DEPLOYMENT_REVISION_ID)") \
		--output benchmarks/m2/current.json
	uv run python -m scripts.render_m2_diagnostics_benchmark \
		benchmarks/m2/current.json benchmarks/m2/current.md

m2-diagnostics-render:
	@test -f benchmarks/m2/current.json || (echo "benchmarks/m2/current.json does not exist" >&2; exit 2)
	uv run python -m scripts.render_m2_diagnostics_benchmark \
		benchmarks/m2/current.json benchmarks/m2/current.md

m2-diagnostics-check:
	@test -f benchmarks/m2/current.json || (echo "benchmarks/m2/current.json does not exist" >&2; exit 2)
	@test -f benchmarks/m2/current.md || (echo "benchmarks/m2/current.md does not exist" >&2; exit 2)
	uv run python -m scripts.render_m2_diagnostics_benchmark \
		benchmarks/m2/current.json benchmarks/m2/current.md --check

evaluation-infra-status:
	uv run python -m scripts.evaluation_infra_status --output "$(EVALUATION_INFRA_JSON)"
	uv run python scripts/render_evaluation_infra_status.py "$(EVALUATION_INFRA_JSON)" --output "$(EVALUATION_INFRA_MD)"

evaluation-infra-render:
	@test -f "$(EVALUATION_INFRA_JSON)" || (echo "$(EVALUATION_INFRA_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_evaluation_infra_status.py "$(EVALUATION_INFRA_JSON)" --output "$(EVALUATION_INFRA_MD)"

evaluation-infra-check:
	@test -f "$(EVALUATION_INFRA_JSON)" || (echo "$(EVALUATION_INFRA_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_evaluation_infra_status.py "$(EVALUATION_INFRA_JSON)" --output "$(EVALUATION_INFRA_MD)" --check

retrieval-benchmark:
	@test -n "$(RETRIEVAL_SUITE_REVISION)" || (echo "RETRIEVAL_SUITE_REVISION is required" >&2; exit 2)
	uv run python scripts/run_retrieval_benchmark.py \
		--suite-revision "$(RETRIEVAL_SUITE_REVISION)" \
		$(if $(RETRIEVAL_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(RETRIEVAL_DEPLOYMENT_REVISION_ID)") \
		--output "$(RETRIEVAL_BENCHMARK_JSON)"
	uv run python scripts/render_retrieval_benchmark.py "$(RETRIEVAL_BENCHMARK_JSON)" --output "$(RETRIEVAL_BENCHMARK_MD)"

retrieval-benchmark-render:
	@test -f "$(RETRIEVAL_BENCHMARK_JSON)" || (echo "$(RETRIEVAL_BENCHMARK_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_retrieval_benchmark.py "$(RETRIEVAL_BENCHMARK_JSON)" --output "$(RETRIEVAL_BENCHMARK_MD)"

retrieval-benchmark-check:
	@test -f "$(RETRIEVAL_BENCHMARK_JSON)" || (echo "$(RETRIEVAL_BENCHMARK_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_retrieval_benchmark.py "$(RETRIEVAL_BENCHMARK_JSON)" --output "$(RETRIEVAL_BENCHMARK_MD)" --check

security-benchmark:
	@test -n "$(SECURITY_SUITE_REVISION)" || (echo "SECURITY_SUITE_REVISION is required" >&2; exit 2)
	uv run python scripts/run_security_benchmark.py \
		--suite-revision "$(SECURITY_SUITE_REVISION)" \
		$(if $(SECURITY_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(SECURITY_DEPLOYMENT_REVISION_ID)") \
		--output "$(SECURITY_BENCHMARK_JSON)"
	uv run python scripts/render_security_benchmark.py "$(SECURITY_BENCHMARK_JSON)" --output "$(SECURITY_BENCHMARK_MD)"

security-benchmark-render:
	@test -f "$(SECURITY_BENCHMARK_JSON)" || (echo "$(SECURITY_BENCHMARK_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_security_benchmark.py "$(SECURITY_BENCHMARK_JSON)" --output "$(SECURITY_BENCHMARK_MD)"

security-benchmark-check:
	@test -f "$(SECURITY_BENCHMARK_JSON)" || (echo "$(SECURITY_BENCHMARK_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_security_benchmark.py "$(SECURITY_BENCHMARK_JSON)" --output "$(SECURITY_BENCHMARK_MD)" --check

security-adversarial-benchmark:
	@test -n "$(SECURITY_ADVERSARIAL_SUITE_REVISION)" || (echo "SECURITY_ADVERSARIAL_SUITE_REVISION is required" >&2; exit 2)
	uv run python -m scripts.run_security_adversarial_benchmark \
		--suite-revision "$(SECURITY_ADVERSARIAL_SUITE_REVISION)" \
		$(if $(SECURITY_ADVERSARIAL_DEPLOYMENT_REVISION_ID),--deployment-revision-id "$(SECURITY_ADVERSARIAL_DEPLOYMENT_REVISION_ID)") \
		--output "$(SECURITY_ADVERSARIAL_JSON)"
	uv run python scripts/render_security_adversarial_benchmark.py \
		"$(SECURITY_ADVERSARIAL_JSON)" --output "$(SECURITY_ADVERSARIAL_MD)"

security-adversarial-render:
	@test -f "$(SECURITY_ADVERSARIAL_JSON)" || (echo "$(SECURITY_ADVERSARIAL_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_security_adversarial_benchmark.py \
		"$(SECURITY_ADVERSARIAL_JSON)" --output "$(SECURITY_ADVERSARIAL_MD)"

security-adversarial-check:
	@test -f "$(SECURITY_ADVERSARIAL_JSON)" || (echo "$(SECURITY_ADVERSARIAL_JSON) does not exist" >&2; exit 2)
	uv run python scripts/render_security_adversarial_benchmark.py \
		"$(SECURITY_ADVERSARIAL_JSON)" --output "$(SECURITY_ADVERSARIAL_MD)" --check

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

investigation-probe:
	@test -n "$(INVESTIGATION_PROBE_CVE_ID)" || (echo "INVESTIGATION_PROBE_CVE_ID is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_GOAL)" || (echo "INVESTIGATION_PROBE_GOAL is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_QUESTION)" || (echo "INVESTIGATION_PROBE_QUESTION is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_SUITE_ID)" || (echo "INVESTIGATION_PROBE_SUITE_ID is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_SUITE_REVISION)" || (echo "INVESTIGATION_PROBE_SUITE_REVISION is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_MANIFEST)" || (echo "INVESTIGATION_PROBE_MANIFEST is required" >&2; exit 2)
	@test -n "$(INVESTIGATION_PROBE_OUTPUT)" || (echo "INVESTIGATION_PROBE_OUTPUT is required" >&2; exit 2)
	uv run python -m scripts.run_prospective_investigation_probe \
		--cve-id "$(INVESTIGATION_PROBE_CVE_ID)" \
		--goal "$(INVESTIGATION_PROBE_GOAL)" \
		--evidence-question "$(INVESTIGATION_PROBE_QUESTION)" \
		--suite-id "$(INVESTIGATION_PROBE_SUITE_ID)" \
		--suite-revision "$(INVESTIGATION_PROBE_SUITE_REVISION)" \
		--deadline-seconds "$(INVESTIGATION_PROBE_DEADLINE_SECONDS)" \
		--agent-turns "$(INVESTIGATION_PROBE_AGENT_TURNS)" \
		--tool-calls "$(INVESTIGATION_PROBE_TOOL_CALLS)" \
		--manifest-output "$(INVESTIGATION_PROBE_MANIFEST)" \
		--output "$(INVESTIGATION_PROBE_OUTPUT)"

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

evidence-doc: m1-render-doc m2-diagnostics-render qa-preflight investigation-readiness evaluation-infra-render retrieval-benchmark-render security-benchmark-render security-adversarial-render competition-render-doc data-plane-metrics-render readme-evidence

evidence-doc-check: m1-doc-check m2-diagnostics-check qa-preflight-doc-check investigation-readiness-doc-check evaluation-infra-check retrieval-benchmark-check security-benchmark-check security-adversarial-check fault-recovery-doc-check competition-doc-check data-plane-metrics-check readme-evidence-check

dev-up:
	docker compose -f deploy/docker-compose.yml up -d --wait postgres redis-broker redis-cache redis-task-bus

runtime-config-check:
	docker compose -f deploy/docker-compose.yml --profile runtime config --quiet

dev-runtime-up: dev-up migrate sync-sources sync-skills runtime-config-check
	docker compose -f deploy/docker-compose.yml --profile runtime up -d --build \
		scheduler task-event-dispatcher task-event-scheduler worker-collection worker

# Long-lived M1-M3 data plane. This intentionally does not configure or require a
# model provider; with SECFUSION_MODEL_* unset, document indexing stays lexical
# and Investigation/QA model calls are not started by this target.
data-plane-up: dev-runtime-up

data-plane-down: dev-runtime-down

data-plane-status:
	docker compose -f deploy/docker-compose.yml --profile runtime ps \
		postgres redis-broker redis-cache redis-task-bus \
		scheduler task-event-dispatcher task-event-scheduler worker-collection worker
	uv run python -m scripts.data_plane_status

data-plane-metrics:
	uv run python -m scripts.data_plane_status --output benchmarks/data-plane/current.json >/dev/null
	uv run python scripts/render_data_plane_metrics.py benchmarks/data-plane/current.json --output benchmarks/data-plane/current.md
	uv run python scripts/render_readme_evidence.py
	@if [ -d "$(WIKI_PATH)/site/data" ]; then $(MAKE) data-plane-site; fi

data-plane-metrics-render:
	@test -f benchmarks/data-plane/current.json || (echo "benchmarks/data-plane/current.json does not exist" >&2; exit 2)
	uv run python scripts/render_data_plane_metrics.py benchmarks/data-plane/current.json --output benchmarks/data-plane/current.md

data-plane-metrics-check:
	@test -f benchmarks/data-plane/current.json || (echo "benchmarks/data-plane/current.json does not exist" >&2; exit 2)
	uv run python scripts/render_data_plane_metrics.py benchmarks/data-plane/current.json --output benchmarks/data-plane/current.md --check

data-plane-site:
	@test -f benchmarks/data-plane/current.json || (echo "benchmarks/data-plane/current.json does not exist" >&2; exit 2)
	@test -d "$(WIKI_PATH)/site/data" || (echo "$(WIKI_PATH)/site/data does not exist" >&2; exit 2)
	uv run python scripts/render_data_plane_site.py benchmarks/data-plane/current.json --output "$(WIKI_PATH)/site/data/data-plane-runtime.js"

data-plane-site-check:
	@test -f "$(WIKI_PATH)/site/data/data-plane-runtime.js" || (echo "data-plane website projection does not exist" >&2; exit 2)
	uv run python scripts/render_data_plane_site.py benchmarks/data-plane/current.json --output "$(WIKI_PATH)/site/data/data-plane-runtime.js" --check

data-plane-logs:
	docker compose -f deploy/docker-compose.yml --profile runtime logs --tail=200 \
		scheduler task-event-dispatcher task-event-scheduler worker-collection worker

dev-runtime-down:
	docker compose -f deploy/docker-compose.yml --profile runtime stop \
		scheduler task-event-dispatcher task-event-scheduler worker-collection worker

runtime-status:
	docker compose -f deploy/docker-compose.yml --profile runtime ps \
		scheduler task-event-dispatcher task-event-scheduler worker-collection worker

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
	docker compose -f deploy/docker-compose.yml --profile localstack up -d --wait localstack-s3

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
