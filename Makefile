.PHONY: sync lint format typecheck test check dev-up dev-down migrate sync-sources worker scheduler probe-nvd promote-hot

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
