from celery import Celery

from apps.runtime_models import register_runtime_models
from packages.shared.config import get_settings

register_runtime_models()
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
        "secfusion.projection.*": {"queue": "indexing"},
        "secfusion.indexing.*": {"queue": "indexing"},
    },
)
