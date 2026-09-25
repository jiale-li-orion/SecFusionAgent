.PHONY: sync lint format typecheck test check site-check site-status dev-up dev-down migrate sync-sources worker scheduler probe-nvd promote-hot

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

site-check:
	python3 scripts/validate_site.py --site $(WIKI_PATH)/site

site-status:
	python3 scripts/build_site_status.py --repo . --wiki $(WIKI_PATH) --output $(SITE_STATUS_OUTPUT)

dev-up:
	docker compose -f deploy/docker-compose.yml up -d postgres redis-broker redis-cache minio

dev-down:
	docker compose -f deploy/docker-compose.yml down

migrate:
	uv run alembic upgrade head

sync-sources:
	uv run python -m scripts.sync_sources

worker:
	uv run celery -A apps.worker.celery_app:celery_app worker -l INFO -Q collection

scheduler:
	uv run python -m apps.worker.scheduler

probe-nvd:
	uv run python -m scripts.probe_nvd_hot --limit 20

promote-hot:
	uv run python -m scripts.promote_hot_bug $(CVE)
