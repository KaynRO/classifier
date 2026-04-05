import json
import os
import sys
import traceback
from datetime import datetime, timezone
from uuid import UUID

import redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.tasks.celery_app import celery_app
from app.models import Job, Domain, Vendor, CheckResult, CheckHistory

# Database setup for sync Celery tasks
DATABASE_URL = os.environ.get("DATABASE_URL_SYNC", "postgresql://classifier:changeme@postgres:5432/classifier")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_redis():
    return redis.from_url(REDIS_URL)


def publish_update(job_id: str, vendor_name: str, status: str, category: str = None, error: str = None):
    r = get_redis()
    msg = {
        "job_id": job_id,
        "vendor": vendor_name,
        "status": status,
        "category": category,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    r.publish("job_updates", json.dumps(msg))


def update_job_progress(db: Session, job_id: str, vendor_name: str, status: str):
    job = db.get(Job, UUID(job_id))
    if job:
        progress = dict(job.progress or {})
        progress[vendor_name] = status
        job.progress = progress
        db.commit()


def save_check_result(
    db: Session, domain_id: str, vendor_id: int, action_type: str,
    status: str, category: str = None, reputation: str = None,
    error_message: str = None, raw_response: dict = None
):
    # Upsert check_results (latest)
    existing = db.execute(
        select(CheckResult).where(
            CheckResult.domain_id == UUID(domain_id),
            CheckResult.vendor_id == vendor_id,
            CheckResult.action_type == action_type,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        existing.status = status
        existing.category = category
        existing.reputation = reputation
        existing.error_message = error_message
        existing.raw_response = raw_response
        existing.completed_at = now
        existing.attempts = (existing.attempts or 0) + 1
    else:
        result = CheckResult(
            domain_id=UUID(domain_id),
            vendor_id=vendor_id,
            action_type=action_type,
            status=status,
            category=category,
            reputation=reputation,
            error_message=error_message,
            raw_response=raw_response,
            started_at=now,
            completed_at=now,
            attempts=1,
        )
        db.add(result)

    # Append to history
    history = CheckHistory(
        domain_id=UUID(domain_id),
        vendor_id=vendor_id,
        action_type=action_type,
        status=status,
        category=category,
        reputation=reputation,
        error_message=error_message,
        raw_response=raw_response,
        started_at=now,
        completed_at=now,
        attempts=1,
    )
    db.add(history)
    db.commit()


@celery_app.task(name="app.tasks.vendor_tasks.run_vendor_check", bind=True, max_retries=0)
def run_vendor_check(self, job_id: str, domain_id: str, domain_name: str,
                     vendor_name: str, vendor_id: int, action_type: str,
                     email: str = None, category: str = None):
    db = SessionLocal()
    try:
        update_job_progress(db, job_id, vendor_name, "running")
        publish_update(job_id, vendor_name, "running")

        # Import and run the appropriate vendor module
        from app.tasks.classifier_bridge import run_vendor_operation
        result = run_vendor_operation(
            vendor_name=vendor_name,
            domain=domain_name,
            action=action_type,
            email=email,
            category=category,
        )

        save_check_result(
            db, domain_id, vendor_id, action_type,
            status="success",
            category=result.get("category"),
            reputation=result.get("reputation"),
            raw_response=result,
        )
        update_job_progress(db, job_id, vendor_name, "success")
        publish_update(job_id, vendor_name, "success", category=result.get("category"))

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        save_check_result(
            db, domain_id, vendor_id, action_type,
            status="failed",
            error_message=error_msg,
        )
        update_job_progress(db, job_id, vendor_name, "failed")
        publish_update(job_id, vendor_name, "failed", error=str(e))

    finally:
        db.close()


@celery_app.task(name="app.tasks.vendor_tasks.run_domain_job", bind=True, max_retries=0)
def run_domain_job(self, job_id: str, domain_id: str, domain_name: str,
                   action_type: str, vendor_filter: str = None):
    db = SessionLocal()
    try:
        # Get applicable vendors
        query = select(Vendor).where(Vendor.is_active == True)

        if action_type == "reputation":
            query = query.where(Vendor.vendor_type == "reputation")
        elif action_type in ("check", "submit"):
            query = query.where(Vendor.vendor_type == "category")
            if action_type == "submit":
                query = query.where(Vendor.supports_submit == True)

        if vendor_filter:
            query = query.where(Vendor.name == vendor_filter)

        vendors = db.execute(query).scalars().all()

        # Get domain details for email/category
        domain = db.get(Domain, UUID(domain_id))
        email = domain.email_for_submit if domain else None
        desired_category = domain.desired_category if domain else None

        # Fan out: dispatch one task per vendor
        from celery import group
        tasks = []
        for v in vendors:
            tasks.append(
                run_vendor_check.s(
                    job_id, domain_id, domain_name,
                    v.name, v.id, action_type,
                    email, desired_category,
                )
            )

        if tasks:
            job_group = group(tasks)
            job_group.apply_async()

        # Update job status
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
