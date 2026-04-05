from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Vendor, User
from app.schemas import VendorResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])


@router.get("", response_model=list[VendorResponse])
async def list_vendors(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Vendor).order_by(Vendor.vendor_type, Vendor.name))
    return [VendorResponse.model_validate(v) for v in result.scalars().all()]
