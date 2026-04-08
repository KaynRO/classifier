from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Job, Domain, Vendor, User, CheckResult, CheckHistory
from app.schemas import JobCreate, JobResponse, PaginatedResponse
from app.auth import get_current_user, require_admin
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


async def _create_job(
    db: AsyncSession, domain_id: UUID, action_type: str,
    vendor_filter: str | None, user_id: UUID
) -> Job:
    # Verify domain exists
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    job = Job(
        domain_id=domain_id,
        action_type=action_type,
        vendor_filter=vendor_filter,
        status="pending",
        requested_by=user_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery
    task = celery_app.send_task(
        "app.tasks.vendor_tasks.run_domain_job",
        args=[str(job.id), str(domain_id), domain.domain, action_type, vendor_filter],
    )
    job.celery_task_id = task.id
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)

    return job


@router.post("/check", response_model=JobResponse, status_code=201)
async def create_check_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = await _create_job(db, data.domain_id, "check", data.vendor, user.id)
    return JobResponse.model_validate(job)


@router.post("/reputation", response_model=JobResponse, status_code=201)
async def create_reputation_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = await _create_job(db, data.domain_id, "reputation", data.vendor, user.id)
    return JobResponse.model_validate(job)


@router.post("/submit", response_model=JobResponse, status_code=201)
async def create_submit_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    job = await _create_job(db, data.domain_id, "submit", data.vendor, user.id)
    return JobResponse.model_validate(job)


@router.post("/bulk-check", response_model=list[JobResponse], status_code=201)
async def bulk_check(
    vendor: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await db.execute(select(Domain).where(Domain.is_active == True))
    domains = result.scalars().all()
    if not domains:
        raise HTTPException(status_code=404, detail="No active domains found")

    jobs = []
    for domain in domains:
        job = await _create_job(db, domain.id, "check", vendor, user.id)
        jobs.append(JobResponse.model_validate(job))
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


async def restore_previous_state(db: AsyncSession, cr: CheckResult) -> None:
    # Restore last known non-running/cancelled state from check_history; if none
    # exists, delete the row so the UI shows "never checked".
    prior = await db.execute(
        select(CheckHistory)
        .where(
            CheckHistory.domain_id == cr.domain_id,
            CheckHistory.vendor_id == cr.vendor_id,
            CheckHistory.action_type == cr.action_type,
            CheckHistory.status.not_in(["running", "pending", "cancelled"]),
        )
        .order_by(CheckHistory.completed_at.desc().nullslast(), CheckHistory.created_at.desc())
        .limit(1)
    )
    prev = prior.scalar_one_or_none()
    if prev is None:
        await db.delete(cr)
        return
    cr.status = prev.status
    cr.category = prev.category
    cr.reputation = prev.reputation
    cr.error_message = prev.error_message
    cr.raw_response = prev.raw_response
    cr.started_at = prev.started_at
    cr.completed_at = prev.completed_at


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Revoke the Celery task
    if job.celery_task_id:
        try:
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    # Restore each running check_result to its previous known state (from history)
    running_cr = await db.execute(
        select(CheckResult).where(
            CheckResult.domain_id == job.domain_id,
            CheckResult.status.in_(["running", "pending"]),
        )
    )
    for cr in running_cr.scalars().all():
        await restore_previous_state(db, cr)

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return JobResponse.model_validate(job)


@router.post("/cancel-vendor")
async def cancel_vendor_job(
    domain_id: UUID,
    vendor: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vendor_result = await db.execute(select(Vendor).where(Vendor.name == vendor))
    v = vendor_result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor}' not found")

    # Find any running/pending check_result rows for this vendor (check + submit + reputation)
    cr_result = await db.execute(
        select(CheckResult).where(
            CheckResult.domain_id == domain_id,
            CheckResult.vendor_id == v.id,
            CheckResult.status.in_(["running", "pending"]),
        )
    )
    crs = cr_result.scalars().all()
    if not crs:
        return {"detail": "No running task for this vendor"}

    # Find the parent job(s) and revoke the Celery task
    jobs_result = await db.execute(
        select(Job).where(
            Job.domain_id == domain_id,
            Job.status.in_(["running", "pending"]),
        ).order_by(Job.started_at.desc())
    )
    for j in jobs_result.scalars().all():
        progress = j.progress or {}
        if vendor in progress:
            if j.celery_task_id:
                try:
                    celery_app.control.revoke(j.celery_task_id, terminate=True, signal="SIGTERM")
                except Exception:
                    pass
            j.status = "cancelled"
            j.completed_at = datetime.now(timezone.utc)

    # Restore each running check_result to its previous known state
    for cr in crs:
        await restore_previous_state(db, cr)

    await db.commit()
    return {"detail": f"Cancelled running task for {vendor}"}


@router.get("", response_model=PaginatedResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str = Query(None),
    domain_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Job)
    if status:
        query = query.where(Job.status == status)
    if domain_id:
        query = query.where(Job.domain_id == domain_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Job.requested_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return PaginatedResponse(
        items=[JobResponse.model_validate(j) for j in jobs],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )
