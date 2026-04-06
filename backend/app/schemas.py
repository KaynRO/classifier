from datetime import datetime
from typing import Optional
from uuid import UUID
import re
import html
from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Auth ---
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8)

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
DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')
VALID_CATEGORIES = {"Business", "Education", "Finance", "Health", "News", "Internet"}

def _sanitize(v: str | None) -> str | None:
    if v is None:
        return None
    return html.escape(v.strip(), quote=True)

class DomainCreate(BaseModel):
    domain: str = Field(min_length=1, max_length=255)
    display_name: Optional[str] = None
    desired_category: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    custom_text: Optional[str] = Field(None, max_length=1000)
    email_for_submit: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower().lstrip("https://").lstrip("http://").rstrip("/")
        if not DOMAIN_RE.match(v):
            raise ValueError("Invalid domain format")
        return v

    @field_validator("desired_category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v and v not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")
        return v

    @field_validator("notes", "custom_text", "display_name")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        return _sanitize(v)

class DomainUpdate(BaseModel):
    display_name: Optional[str] = None
    desired_category: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    custom_text: Optional[str] = Field(None, max_length=1000)

    @field_validator("desired_category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v and v not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")
        return v

    @field_validator("notes", "custom_text", "display_name")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        return _sanitize(v)
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
