#!/bin/bash
set -e

exec xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    celery -A app.tasks.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --queues=classifier \
    --hostname=worker@%h
