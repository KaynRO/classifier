from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Job, Domain, Vendor, User
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
