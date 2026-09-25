import asyncio

from apps.worker.celery_app import celery_app
from packages.monitoring.runtime import execute_collection_run
from packages.shared.config import get_settings


@celery_app.task(name="secfusion.collection.run")
def run_collection(run_id: str) -> str:
    return asyncio.run(execute_collection_run(run_id, get_settings()))
