from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Domain, CheckResult, CheckHistory, User
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
):
    query = select(Domain).where(Domain.is_active == is_active)
    if search:
        query = query.where(Domain.domain.ilike(f"%{search}%"))

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
):
    existing = await db.execute(select(Domain).where(Domain.domain == data.domain))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Domain already exists")

    domain = Domain(**data.model_dump(), created_by=user.id)
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
):
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
async def delete_domain(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain.is_active = False
    await db.commit()


@router.get("/{domain_id}/results", response_model=list[CheckResultResponse])
async def get_domain_results(domain_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
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
):
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
