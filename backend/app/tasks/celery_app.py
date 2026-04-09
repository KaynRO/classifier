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
    # acks_late=False: if the worker dies mid-task, Celery does NOT re-deliver.
    # We'd rather fail fast and let the user re-trigger than silently re-run
    # a stale browser-automation task from attempt 1 on a fresh worker.
    task_acks_late=False,
    task_time_limit=1500,
    task_soft_time_limit=1440,
    task_default_rate_limit="6/m",
    task_routes={
        "app.tasks.vendor_tasks.*": {"queue": "classifier"},
    },
)

celery_app.conf.include = ["app.tasks.vendor_tasks"]
