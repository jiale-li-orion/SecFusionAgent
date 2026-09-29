.PHONY: sync lint format typecheck test check site-check site-status dev-up dev-down migrate sync-sources sync-skills worker worker-collection scheduler task-event-dispatcher task-event-scheduler probe-nvd promote-hot product-check

WIKI_PATH ?= ../SecFusionAgent.wiki
SITE_STATUS_OUTPUT ?= $(WIKI_PATH)/site/project-status.json

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

dev-up:
	docker compose -f deploy/docker-compose.yml up -d postgres redis-broker redis-cache redis-task-bus minio

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
	docker compose -f deploy/docker-compose.yml down

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
	docker compose -f deploy/docker-compose.yml --profile integration up -d --wait localstack-s3

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
