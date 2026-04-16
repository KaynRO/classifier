import csv, io
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Domain, Vendor, CheckResult, CheckHistory, User
from app.schemas import (
    DomainCreate, DomainUpdate, DomainResponse, CheckResultResponse, PaginatedResponse
)
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


@router.get("", response_model=PaginatedResponse)
async def list_domains(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=255),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = select(Domain).where(Domain.is_active == is_active)
    if search:
        escaped = search.replace('%', '\\%').replace('_', '\\_')
        query = query.where(Domain.domain.ilike(f"%{escaped}%", escape='\\'))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Domain.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    domains = result.scalars().all()

    return PaginatedResponse(
        items=[DomainResponse.model_validate(d) for d in domains],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )


@router.post("", response_model=DomainResponse, status_code=201)
async def create_domain(
    data: DomainCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> DomainResponse:
    existing = await db.execute(
        select(Domain).where(Domain.domain == data.domain, Domain.is_active == True)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Domain already exists")

    domain = Domain(**data.model_dump(), created_by=user.id)
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> DomainResponse:
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return DomainResponse.model_validate(domain)


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: UUID,
    data: DomainUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> DomainResponse:
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(domain, key, value)

    await db.commit()
    await db.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.delete("/{domain_id}", status_code=204)
async def delete_domain(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)) -> None:
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain.is_active = False
    await db.commit()


@router.get("/{domain_id}/results", response_model=list[CheckResultResponse])
async def get_domain_results(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> list[CheckResultResponse]:
    result = await db.execute(
        select(CheckResult)
        .options(selectinload(CheckResult.vendor))
        .where(CheckResult.domain_id == domain_id)
        .order_by(CheckResult.vendor_id)
    )
    return [CheckResultResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{domain_id}/history", response_model=PaginatedResponse)
async def get_domain_history(
    domain_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    vendor: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = select(CheckHistory).where(CheckHistory.domain_id == domain_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(CheckHistory.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[CheckResultResponse.model_validate(h) for h in items],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )


@router.get("/export/csv")
async def export_domains_csv(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    domains = (await db.execute(
        select(Domain).where(Domain.is_active == True).order_by(Domain.domain)
    )).scalars().all()

    vendors = (await db.execute(
        select(Vendor).where(Vendor.is_active == True).order_by(Vendor.vendor_type, Vendor.name)
    )).scalars().all()

    all_results = (await db.execute(
        select(CheckResult).options(selectinload(CheckResult.vendor))
    )).scalars().all()

    all_history = (await db.execute(
        select(CheckHistory).order_by(CheckHistory.created_at.desc())
    )).scalars().all()

    result_map = {}
    for r in all_results:
        result_map[(str(r.domain_id), r.vendor_id)] = r

    history_map: dict[str, list] = {}
    for h in all_history:
        key = str(h.domain_id)
        if key not in history_map:
            history_map[key] = []
        history_map[key].append(h)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== CURRENT STATUS ==="])
    header = ["Domain", "Desired Category", "Email", "Notes"]
    for v in vendors:
        header.extend([f"{v.display_name} - Category", f"{v.display_name} - Reputation", f"{v.display_name} - Status", f"{v.display_name} - Last Check"])
    writer.writerow(header)

    for d in domains:
        row = [d.domain, d.desired_category or "", d.email_for_submit or "", d.notes or ""]
        for v in vendors:
            r = result_map.get((str(d.id), v.id))
            if r:
                row.extend([
                    r.category or "",
                    r.reputation or "",
                    r.status or "",
                    r.completed_at.strftime("%Y-%m-%d %H:%M") if r.completed_at else "",
                ])
            else:
                row.extend(["", "", "Not Checked", ""])
        writer.writerow(row)

    writer.writerow([])
    writer.writerow([])

    writer.writerow(["=== CHECK HISTORY ==="])
    writer.writerow(["Domain", "Vendor", "Action", "Status", "Category", "Reputation", "Error", "Date"])

    vendor_lookup = {v.id: v.display_name for v in vendors}
    domain_lookup = {str(d.id): d.domain for d in domains}

    for h in all_history:
        domain_name = domain_lookup.get(str(h.domain_id), "Unknown")
        vendor_name = vendor_lookup.get(h.vendor_id, "Unknown")
        writer.writerow([
            domain_name,
            vendor_name,
            h.action_type,
            h.status,
            h.category or "",
            h.reputation or "",
            (h.error_message or "")[:200],
            h.created_at.strftime("%Y-%m-%d %H:%M:%S") if h.created_at else "",
        ])

    output.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=classifier_export_{timestamp}.csv"},
    )
