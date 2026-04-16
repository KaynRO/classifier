import json, os, traceback, redis
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.tasks.celery_app import celery_app
from app.models import Job, Domain, Vendor, CheckResult, CheckHistory

DATABASE_URL = os.environ.get("DATABASE_URL_SYNC", "postgresql://classifier:changeme@postgres:5432/classifier")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL)


def publish_update(job_id: str, vendor_name: str, status: str, category: str = None, error: str = None) -> None:
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


def update_job_progress(db: Session, job_id: str, vendor_name: str, status: str) -> None:
    from sqlalchemy import text
    db.execute(
        text("UPDATE jobs SET progress = COALESCE(progress, '{}'::jsonb) || :new_val WHERE id = :job_id"),
        {"new_val": json.dumps({vendor_name: status}), "job_id": job_id}
    )
    db.commit()


def sweep_orphan_running(db: Session, domain_id: str, vendor_id: int, action_type: str) -> None:
    from sqlalchemy import update as sql_update
    now = datetime.now(timezone.utc)
    db.execute(
        sql_update(CheckResult)
        .where(
            CheckResult.domain_id == UUID(domain_id),
            CheckResult.vendor_id == vendor_id,
            CheckResult.action_type == action_type,
            CheckResult.status.in_(["running", "pending"]),
        )
        .values(
            status="failed",
            error_message="Auto-failed: previous task was killed before completing",
            completed_at=now,
        )
    )
    db.commit()


def save_check_result(
    db: Session, domain_id: str, vendor_id: int, action_type: str,
    status: str, category: str = None, reputation: str = None,
    error_message: str = None, raw_response: dict = None
) -> None:
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
        if status != "running":
            existing.category = category
            existing.reputation = reputation
            existing.error_message = error_message
            existing.raw_response = raw_response
            existing.completed_at = now
            existing.attempts = (existing.attempts or 0) + 1
        else:
            existing.started_at = now
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
                     email: str = None, category: str = None) -> dict:
    import io, logging, re, time as task_time

    db = SessionLocal()
    start_time = task_time.time()

    log_capture = io.StringIO()

    class CleanFormatter(logging.Formatter):
        ANSI_RE = re.compile(r'\x1B\[[0-9;]*m')

        def format(self, record: logging.LogRecord) -> str:
            return self.ANSI_RE.sub('', super().format(record))

    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(CleanFormatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))

    classifier_loggers = []
    for name in [f"modules.{vendor_name}", "helpers.captcha_dual_solver"]:
        lg = logging.getLogger(name)
        lg.addHandler(log_handler)
        classifier_loggers.append(lg)

    try:
        sweep_orphan_running(db, domain_id, vendor_id, action_type)

        update_job_progress(db, job_id, vendor_name, "running")
        publish_update(job_id, vendor_name, "running")

        save_check_result(
            db, domain_id, vendor_id, action_type,
            status="running",
        )

        from app.tasks.classifier_bridge import run_vendor_operation
        result = run_vendor_operation(
            vendor_name=vendor_name,
            domain=domain_name,
            action=action_type,
            email=email,
            category=category,
        )

        elapsed = round(task_time.time() - start_time, 1)
        logs = log_capture.getvalue()
        result["logs"] = logs
        result["duration_seconds"] = elapsed

        final_status = "failed" if result.get("status") == "failed" else "success"
        save_check_result(
            db, domain_id, vendor_id, action_type,
            status=final_status,
            category=result.get("category"),
            reputation=result.get("reputation"),
            error_message=result.get("error"),
            raw_response=result,
        )
        update_job_progress(db, job_id, vendor_name, final_status)
        publish_update(job_id, vendor_name, final_status, category=result.get("category"), error=result.get("error"))
        return {"vendor": vendor_name, "status": final_status, "duration": elapsed}

    except Exception as e:
        elapsed = round(task_time.time() - start_time, 1)
        logs = log_capture.getvalue()
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        save_check_result(
            db, domain_id, vendor_id, action_type,
            status="failed",
            error_message=error_msg,
            raw_response={"logs": logs, "duration_seconds": elapsed},
        )
        update_job_progress(db, job_id, vendor_name, "failed")
        publish_update(job_id, vendor_name, "failed", error=str(e))
        return {"vendor": vendor_name, "status": "failed", "duration": elapsed}

    finally:
        for lg in classifier_loggers:
            lg.removeHandler(log_handler)
        db.close()


def finalize_orphan_rows(db: Session, job_id: str) -> None:
    from sqlalchemy import update as sql_update
    job = db.get(Job, UUID(job_id))
    if not job:
        return
    now = datetime.now(timezone.utc)
    db.execute(
        sql_update(CheckResult)
        .where(
            CheckResult.domain_id == job.domain_id,
            CheckResult.action_type == job.action_type,
            CheckResult.status.in_(["running", "pending"]),
        )
        .values(
            status="failed",
            error_message="Auto-failed: task was killed before completing",
            completed_at=now,
        )
    )
    db.commit()


@celery_app.task(name="app.tasks.vendor_tasks.finalize_job")
def finalize_job(results: list, job_id: str) -> None:
    db = SessionLocal()
    try:
        finalize_orphan_rows(db, job_id)
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        publish_update(job_id, "__job__", "completed")
    except Exception:
        pass
    finally:
        db.close()


@celery_app.task(name="app.tasks.vendor_tasks.finalize_job_error", bind=True)
def finalize_job_error(self, *args, **kwargs) -> None:
    job_id = kwargs.get("job_id") or (args[-1] if args else None)
    if not job_id:
        return
    exc_str = ""
    for a in args:
        if isinstance(a, BaseException):
            exc_str = str(a)
            break
    db = SessionLocal()
    try:
        finalize_orphan_rows(db, job_id)
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        publish_update(job_id, "__job__", "failed", error=exc_str or "task killed")
    except Exception:
        pass
    finally:
        db.close()


@celery_app.task(name="app.tasks.vendor_tasks.run_domain_job", bind=True, max_retries=0)
def run_domain_job(self, job_id: str, domain_id: str, domain_name: str,
                   action_type: str, vendor_filter: str = None) -> None:
    db = SessionLocal()
    try:
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

        domain = db.get(Domain, UUID(domain_id))
        email = domain.email_for_submit if domain else None
        desired_category = domain.desired_category if domain else None

        from celery import chord
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
            callback = finalize_job.s(job_id)
            callback.set(link_error=finalize_job_error.s(job_id))
            chord(tasks)(callback)
        else:
            job = db.get(Job, UUID(job_id))
            if job:
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()

        job = db.get(Job, UUID(job_id))
        if job and job.status != "completed":
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"run_domain_job failed: {e}", exc_info=True)
        job = db.get(Job, UUID(job_id))
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
