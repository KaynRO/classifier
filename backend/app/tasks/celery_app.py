import os
from celery import Celery

celery_app = Celery(
    "classifier_worker",
    broker=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    task_default_rate_limit="6/m",
    task_routes={
        "app.tasks.vendor_tasks.*": {"queue": "classifier"},
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
