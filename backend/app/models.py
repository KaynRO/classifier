import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # admin, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Domain(Base):
    __tablename__ = "domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255))
    desired_category = Column(String(50))
    notes = Column(Text)
    custom_text = Column(Text)
    email_for_submit = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    results = relationship("CheckResult", back_populates="domain", cascade="all, delete-orphan")
    history = relationship("CheckHistory", back_populates="domain", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="domain", cascade="all, delete-orphan")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    vendor_type = Column(String(20), nullable=False)  # category, reputation
    supports_check = Column(Boolean, default=True)
    supports_submit = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    results = relationship("CheckResult", back_populates="vendor")


class CheckResult(Base):
    __tablename__ = "check_results"
    __table_args__ = (
        UniqueConstraint("domain_id", "vendor_id", "action_type", name="uq_check_result"),
        Index("idx_check_results_domain", "domain_id"),
        Index("idx_check_results_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    action_type = Column(String(20), nullable=False)  # check, reputation, submit
    status = Column(String(20), nullable=False, default="pending")  # pending, running, success, failed
    category = Column(String(255))
    reputation = Column(String(255))
    raw_response = Column(JSONB)
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    domain = relationship("Domain", back_populates="results")
    vendor = relationship("Vendor", back_populates="results")


class CheckHistory(Base):
    __tablename__ = "check_history"
    __table_args__ = (
        Index("idx_check_history_domain", "domain_id"),
        Index("idx_check_history_created", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    action_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    category = Column(String(255))
    reputation = Column(String(255))
    raw_response = Column(JSONB)
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    domain = relationship("Domain", back_populates="history")
    vendor = relationship("Vendor")


class AppConfig(Base):
    """Key-value store for runtime configuration (API keys, credentials)."""
    __tablename__ = "app_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_domain", "domain_id"),
        Index("idx_jobs_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(20), nullable=False)  # check, reputation, submit
    vendor_filter = Column(String(50))  # null = all vendors
    status = Column(String(20), nullable=False, default="pending")
    celery_task_id = Column(String(255))
    progress = Column(JSONB, default=dict)
    requested_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    domain = relationship("Domain", back_populates="jobs")
