from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Domain ---
class DomainCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)
    display_name: Optional[str] = None
    desired_category: Optional[str] = None
    notes: Optional[str] = None
    custom_text: Optional[str] = None
    email_for_submit: Optional[str] = None

class DomainUpdate(BaseModel):
    display_name: Optional[str] = None
    desired_category: Optional[str] = None
    notes: Optional[str] = None
    custom_text: Optional[str] = None
    email_for_submit: Optional[str] = None
    is_active: Optional[bool] = None

class DomainResponse(BaseModel):
    id: UUID
    domain: str
    display_name: Optional[str]
    desired_category: Optional[str]
    notes: Optional[str]
    custom_text: Optional[str]
    email_for_submit: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Vendor ---
class VendorResponse(BaseModel):
    id: int
    name: str
    display_name: str
    vendor_type: str
    supports_check: bool
    supports_submit: bool
    is_active: bool

    class Config:
        from_attributes = True


# --- Check Result ---
class CheckResultResponse(BaseModel):
    id: UUID
    domain_id: UUID
    vendor_id: int
    action_type: str
    status: str
    category: Optional[str]
    reputation: Optional[str]
    raw_response: Optional[dict]
    error_message: Optional[str]
    attempts: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    vendor: Optional[VendorResponse] = None

    class Config:
        from_attributes = True


# --- Job ---
class JobCreate(BaseModel):
    domain_id: UUID
    vendor: Optional[str] = None

class JobResponse(BaseModel):
    id: UUID
    domain_id: UUID
    action_type: str
    vendor_filter: Optional[str]
    status: str
    celery_task_id: Optional[str]
    progress: Optional[dict]
    requested_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Dashboard ---
class DashboardSummary(BaseModel):
    total_domains: int
    active_domains: int
    total_vendors: int
    pending_jobs: int
    domains_with_mismatches: int
    last_full_scan: Optional[datetime]

class MatrixCell(BaseModel):
    vendor_name: str
    vendor_display_name: str
    status: Optional[str]
    category: Optional[str]
    reputation: Optional[str]
    last_checked: Optional[datetime]

class MatrixRow(BaseModel):
    domain: DomainResponse
    results: list[MatrixCell]

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
