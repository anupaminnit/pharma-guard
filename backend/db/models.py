"""
SQLAlchemy 2.0 async ORM models for PharmaGuard production database.

Tables:
  users             — authenticated users (Azure AD)
  skus              — drug product SKUs with master label text
  analysis_jobs     — one job per SKU × language × file version
  analysis_results  — LLM output stored as JSONB
  audit_events      — append-only regulatory audit trail
  regulatory_rules  — versioned, region-specific compliance rules
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str]       = mapped_column(String(255), unique=True, nullable=False, index=True)
    azure_oid: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str]        = mapped_column(
        Enum("qa_reviewer", "regulatory_affairs", "local_marketing", "admin", name="user_role"),
        nullable=False, default="local_marketing",
    )
    division: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    allowed_regions: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    is_active: Mapped[bool]  = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs     = relationship("AnalysisJob", back_populates="created_by_user", foreign_keys="AnalysisJob.created_by")
    events   = relationship("AuditEvent", back_populates="user")


# ── SKUs ──────────────────────────────────────────────────────────────────────

class SKU(Base):
    __tablename__ = "skus"

    id: Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_code: Mapped[str]    = mapped_column(String(100), unique=True, nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active_ingredient: Mapped[str] = mapped_column(String(255), nullable=False)
    strength: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dosage_form: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    master_label_text: Mapped[str] = mapped_column(Text, nullable=False)
    master_label_version: Mapped[int] = mapped_column(Integer, default=1)
    veeva_document_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    jobs = relationship("AnalysisJob", back_populates="sku")


# ── Analysis Jobs ─────────────────────────────────────────────────────────────

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=True, index=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    target_language: Mapped[str]    = mapped_column(String(50), nullable=False)
    regulatory_region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "complete", "failed", "needs_review", "stale_rules", name="job_status"),
        nullable=False, default="queued", index=True,
    )
    workflow_state: Mapped[str] = mapped_column(
        Enum("draft", "ai_reviewed", "human_review", "approved", "rejected", name="workflow_state"),
        nullable=False, default="draft",
    )

    # Content hashes for deduplication
    master_label_hash: Mapped[Optional[str]]   = mapped_column(String(64), nullable=True)
    packaging_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    packaging_file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Celery task ID for status polling
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sku            = relationship("SKU", back_populates="jobs")
    created_by_user = relationship("User", back_populates="jobs", foreign_keys=[created_by])
    result         = relationship("AnalysisResult", back_populates="job", uselist=False)
    audit_events   = relationship("AuditEvent", back_populates="job")

    __table_args__ = (
        # Fast lookup for deduplication
        Index("ix_jobs_dedup", "master_label_hash", "packaging_file_hash", "target_language"),
        # Tenant isolation
        Index("ix_jobs_tenant_status", "tenant_id", "status"),
    )


# ── Analysis Results ──────────────────────────────────────────────────────────

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), unique=True, nullable=False, index=True)
    compliance_score: Mapped[float]  = mapped_column(Float, nullable=False)
    overall_status: Mapped[str]      = mapped_column(String(50), nullable=False)
    translation_analysis: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    vision_analysis: Mapped[dict]      = mapped_column(JSONB, nullable=False, default=dict)
    agent_log: Mapped[list]            = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str]               = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    job = relationship("AnalysisJob", back_populates="result")


# ── Audit Events (append-only) ────────────────────────────────────────────────

class AuditEvent(Base):
    """
    Append-only regulatory audit trail.
    Enforce at DB level: REVOKE UPDATE, DELETE ON audit_events FROM app_role;
    """
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(
        Enum("submitted", "reviewed", "approved", "rejected", "exported", "stale_flagged", name="audit_event_type"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    job  = relationship("AnalysisJob", back_populates="audit_events")
    user = relationship("User", back_populates="events")

    __table_args__ = (
        Index("ix_audit_job_time", "job_id", "timestamp"),
    )


# ── Regulatory Rules ──────────────────────────────────────────────────────────

class RegulatoryRule(Base):
    """
    Versioned, region-specific compliance rules.
    One DB row change (with new effective_date) propagates to all future analyses
    without requiring a code deploy.
    """
    __tablename__ = "regulatory_rules"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region: Mapped[str]     = mapped_column(String(50), nullable=False, index=True)
    rule_type: Mapped[str]  = mapped_column(
        Enum("required_element", "font_minimum", "placement", "symbol", "structure", "language", name="rule_type"),
        nullable=False,
    )
    rule_key: Mapped[str]   = mapped_column(String(255), nullable=False)
    rule_value: Mapped[dict] = mapped_column(JSONB, nullable=False)

    effective_date: Mapped[date]       = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_document: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_rules_region_active", "region", "is_active", "effective_date"),
    )
