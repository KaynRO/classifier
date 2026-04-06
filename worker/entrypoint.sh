#!/bin/bash
set -e

export PYTHONUNBUFFERED=1
export DISPLAY=:99

# Start Xvfb in background
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 1

# Run Celery directly (not via xvfb-run, to preserve stdout)
exec celery -A app.tasks.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --queues=classifier \
    --hostname=worker@%h
