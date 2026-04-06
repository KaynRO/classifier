from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Domain, Vendor, CheckResult, Job, User
from app.schemas import (
    DashboardSummary, MatrixRow, MatrixCell, DomainResponse, PaginatedResponse
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    total = (await db.execute(select(func.count(Domain.id)).where(Domain.is_active == True))).scalar() or 0
    active = (await db.execute(select(func.count(Domain.id)).where(Domain.is_active == True))).scalar() or 0
    vendors = (await db.execute(select(func.count(Vendor.id)).where(Vendor.is_active == True))).scalar() or 0
    pending = (await db.execute(
        select(func.count(Job.id)).where(Job.status.in_(["pending", "running"]))
    )).scalar() or 0

    # Count domains where any check result category doesn't match desired_category
    mismatch_q = (
        select(func.count(func.distinct(Domain.id)))
        .join(CheckResult, CheckResult.domain_id == Domain.id)
        .where(
            and_(
                Domain.desired_category.isnot(None),
                CheckResult.category.isnot(None),
                CheckResult.status == "success",
                func.lower(CheckResult.category) != func.lower(Domain.desired_category),
            )
        )
    )
    mismatches = (await db.execute(mismatch_q)).scalar() or 0

    # Last completed job
    last_job = await db.execute(
        select(Job.completed_at)
        .where(Job.status == "completed")
        .order_by(Job.completed_at.desc())
        .limit(1)
    )
    last_scan = last_job.scalar_one_or_none()

    return DashboardSummary(
        total_domains=total,
        active_domains=active,
        total_vendors=vendors,
        pending_jobs=pending,
        domains_with_mismatches=mismatches,
        last_full_scan=last_scan,
    )


@router.get("/matrix", response_model=PaginatedResponse)
async def get_matrix(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Get all active vendors
    vendor_result = await db.execute(
        select(Vendor).where(Vendor.is_active == True).order_by(Vendor.vendor_type, Vendor.name)
    )
    vendors = vendor_result.scalars().all()

    # Get paginated domains
    count_q = select(func.count(Domain.id)).where(Domain.is_active == True)
    total = (await db.execute(count_q)).scalar() or 0

    domain_q = (
        select(Domain)
        .where(Domain.is_active == True)
        .order_by(Domain.domain)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    domain_result = await db.execute(domain_q)
    domains = domain_result.scalars().all()

    # Get all check results for these domains in one query
    domain_ids = [d.id for d in domains]
    if domain_ids:
        results_q = await db.execute(
            select(CheckResult)
            .where(CheckResult.domain_id.in_(domain_ids))
        )
        all_results = results_q.scalars().all()
    else:
        all_results = []

    # Build lookup: (domain_id, vendor_id) -> result
    result_map = {}
    for r in all_results:
        key = (str(r.domain_id), r.vendor_id)
        result_map[key] = r

    # Build matrix rows
    rows = []
    for domain in domains:
        cells = []
        for vendor in vendors:
            r = result_map.get((str(domain.id), vendor.id))
            cells.append(MatrixCell(
                vendor_name=vendor.name,
                vendor_display_name=vendor.display_name,
                status=r.status if r else None,
                category=r.category if r else None,
                reputation=r.reputation if r else None,
                last_checked=r.completed_at if r else None,
            ))
        rows.append(MatrixRow(
            domain=DomainResponse.model_validate(domain),
            results=cells,
        ))

    return PaginatedResponse(
        items=[r.model_dump() for r in rows],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )
