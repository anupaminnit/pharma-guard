"""
Job management API routes.

Endpoints:
    POST /api/jobs                     — submit analysis job (async)
    GET  /api/jobs/{job_id}            — poll status + result
    POST /api/jobs/{job_id}/approve    — approve (qa_reviewer / regulatory_affairs)
    POST /api/jobs/{job_id}/reject     — reject with required comment
    GET  /api/jobs/queue               — review queue (human_review state)
    POST /api/batch                    — enqueue multiple SKU×language combos
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.azure_ad import CurrentUser, require_auth, require_reviewer
from db.models import AnalysisJob, AnalysisResult, AuditEvent
from db.session import get_db

router = APIRouter(prefix="/api", tags=["jobs"])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Submit async job ──────────────────────────────────────────────────────────

@router.post("/jobs")
async def submit_job(
    master_label: str = Form(...),
    target_language: str = Form(default="French"),
    packaging_pdf: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
    request: Request = None,
):
    """
    Enqueue a compliance analysis job. Returns immediately with job_id.
    Poll GET /api/jobs/{job_id} for status and result.
    """
    from tasks.analysis_task import run_compliance_analysis

    file_bytes = await packaging_pdf.read()
    file_hash = _sha256(file_bytes)
    label_hash = _sha256(master_label.encode())

    # ── Deduplication: return cached result if identical job ran within 24h ──
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    dup_stmt = (
        select(AnalysisJob)
        .where(
            AnalysisJob.master_label_hash == label_hash,
            AnalysisJob.packaging_file_hash == file_hash,
            AnalysisJob.target_language == target_language,
            AnalysisJob.status == "complete",
            AnalysisJob.created_at >= cutoff,
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup:
        return {"job_id": str(dup.id), "status": "complete", "cached": True}

    # ── Create job row ────────────────────────────────────────────────────────
    job = AnalysisJob(
        target_language=target_language,
        status="queued",
        master_label_hash=label_hash,
        packaging_file_hash=file_hash,
    )
    db.add(job)
    await db.flush()   # get the ID before committing

    db.add(AuditEvent(
        job_id=job.id,
        user_id=None,  # user.oid not yet mapped to DB UUID in demo mode
        event_type="submitted",
        ip_address=request.client.host if request else None,
    ))
    await db.commit()

    # ── Enqueue Celery task ───────────────────────────────────────────────────
    file_b64 = base64.b64encode(file_bytes).decode()
    run_compliance_analysis.delay(
        job_id=str(job.id),
        master_label=master_label,
        target_language=target_language,
        file_bytes_b64=file_b64,
        file_type=packaging_pdf.content_type or "image/jpeg",
        user_id=None,
    )

    return {"job_id": str(job.id), "status": "queued", "cached": False}


# ── Poll job status ───────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Poll job status. When complete, returns full compliance result."""
    stmt = (
        select(AnalysisJob)
        .where(AnalysisJob.id == uuid.UUID(job_id))
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": str(job.id),
        "status": job.status,
        "workflow_state": job.workflow_state,
        "target_language": job.target_language,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "result": None,
    }

    if job.status == "complete" and job.result:
        r = job.result
        response["result"] = {
            "overall_status":     r.overall_status,
            "compliance_score":   r.compliance_score,
            "translation_analysis": r.translation_analysis,
            "vision_analysis":    r.vision_analysis,
            "agent_log":          r.agent_log,
            "summary":            r.summary,
        }

    return response


# ── Review queue ──────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    workflow_state: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_reviewer),
):
    """List jobs — filterable by status / workflow_state. For review queue UI."""
    stmt = select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(AnalysisJob.status == status)
    if workflow_state:
        stmt = stmt.where(AnalysisJob.workflow_state == workflow_state)

    jobs = (await db.execute(stmt)).scalars().all()
    return [
        {
            "job_id": str(j.id),
            "status": j.status,
            "workflow_state": j.workflow_state,
            "target_language": j.target_language,
            "compliance_score": j.result.compliance_score if j.result else None,
            "overall_status": j.result.overall_status if j.result else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


# ── Approve ───────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: str,
    comment: Optional[str] = Body(default=None, embed=True),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_reviewer),
    request: Request = None,
):
    job = (await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.workflow_state not in ("ai_reviewed", "human_review"):
        raise HTTPException(status_code=409, detail=f"Cannot approve job in state '{job.workflow_state}'")

    job.workflow_state = "approved"
    db.add(AuditEvent(
        job_id=job.id,
        event_type="approved",
        comment=comment,
        ip_address=request.client.host if request else None,
    ))
    await db.commit()
    return {"job_id": job_id, "workflow_state": "approved"}


# ── Reject ────────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/reject")
async def reject_job(
    job_id: str,
    comment: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_reviewer),
    request: Request = None,
):
    if not comment or not comment.strip():
        raise HTTPException(status_code=422, detail="A rejection comment is required.")

    job = (await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.workflow_state = "rejected"
    db.add(AuditEvent(
        job_id=job.id,
        event_type="rejected",
        comment=comment,
        ip_address=request.client.host if request else None,
    ))
    await db.commit()
    return {"job_id": job_id, "workflow_state": "rejected"}


# ── Batch submit ──────────────────────────────────────────────────────────────

@router.post("/batch")
async def submit_batch(
    sku_ids: list[str] = Body(...),
    language: str = Body(...),
    priority: str = Body(default="normal"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_reviewer),
):
    """
    Enqueue analysis for multiple SKUs in one request.
    Each SKU must have a master_label_text in the skus table.
    Returns batch_id and list of job_ids.
    """
    from db.models import SKU
    from tasks.analysis_task import run_compliance_analysis

    job_ids = []
    for sku_id in sku_ids:
        sku = (await db.execute(select(SKU).where(SKU.sku_code == sku_id))).scalar_one_or_none()
        if not sku:
            continue

        job = AnalysisJob(
            sku_id=sku.id,
            target_language=language,
            status="queued",
            master_label_hash=_sha256(sku.master_label_text.encode()),
        )
        db.add(job)
        await db.flush()
        job_ids.append(str(job.id))

        # Note: no file_bytes for batch — requires Veeva Vault integration
        # or pre-uploaded files. Stub enqueue here.

    await db.commit()
    return {"batch_id": str(uuid.uuid4()), "job_ids": job_ids, "language": language}
