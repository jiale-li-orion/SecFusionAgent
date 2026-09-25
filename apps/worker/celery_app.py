from celery import Celery

from packages.shared.config import get_settings

settings = get_settings()

celery_app = Celery(
    "secfusionagent",
    broker=settings.redis_broker_url,
    include=["apps.worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "secfusion.collection.*": {"queue": "collection"},
        "secfusion.normalization.*": {"queue": "normalization"},
        "secfusion.enrichment.*": {"queue": "enrichment"},
        "secfusion.indexing.*": {"queue": "indexing"},
    },
)
