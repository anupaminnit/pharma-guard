"""
Celery task: run the full compliance analysis pipeline.

This wraps the same Vision + Translation agent logic used in main.py,
but executed asynchronously by a worker process. Results are written to
PostgreSQL and the job status is updated throughout.

Usage:
    from tasks.analysis_task import run_compliance_analysis
    task = run_compliance_analysis.delay(job_id=str(job.id), ...)
"""

import base64
import hashlib
import io
import os
import uuid
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from tasks.celery_app import celery_app

load_dotenv()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@celery_app.task(
    bind=True,
    name="tasks.analysis_task.run_compliance_analysis",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,   # warn at 2 min
    time_limit=180,         # kill at 3 min
)
def run_compliance_analysis(
    self,
    job_id: str,
    master_label: str,
    target_language: str,
    file_bytes_b64: str,    # base64-encoded file bytes
    file_type: str,
    user_id: str | None = None,
):
    """
    Main async analysis task. Runs Vision + Translation agents, writes result to DB.

    Args:
        job_id:         UUID of the AnalysisJob row (already created by the API)
        master_label:   English master label text
        target_language: Target language string (e.g. "French")
        file_bytes_b64: Base64-encoded packaging file bytes
        file_type:      MIME type (e.g. "image/jpeg")
        user_id:        UUID of the requesting user (for audit trail)
    """
    # Lazy imports to avoid loading these at worker startup for all tasks
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import select
    from db.models import AnalysisJob, AnalysisResult, AuditEvent
    from agents.translation_agent import TranslationAgent
    from agents.vision_agent import VisionAgent

    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://pharma:pharma@localhost:5432/pharma_guard")
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _run():
        async with SessionLocal() as db:
            # ── Mark job as running ──────────────────────────────────────
            result_row = await db.execute(select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id)))
            job = result_row.scalar_one_or_none()
            if not job:
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.celery_task_id = self.request.id
            await db.commit()

            try:
                # ── Decode file ──────────────────────────────────────────
                file_bytes = base64.b64decode(file_bytes_b64)
                actual_file_type = file_type

                # PDF → JPEG conversion
                if "pdf" in actual_file_type.lower():
                    from pdf2image import convert_from_bytes
                    pages = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=150)
                    buf = io.BytesIO()
                    pages[0].save(buf, format="JPEG", quality=90)
                    file_bytes = buf.getvalue()
                    actual_file_type = "image/jpeg"

                file_b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

                # ── Run agents ───────────────────────────────────────────
                client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                translation_agent = TranslationAgent(client)
                vision_agent = VisionAgent(client)

                agent_log = []

                extracted_text, _ = vision_agent.extract_text_from_image(file_b64, actual_file_type, target_language)
                agent_log.append({"agent": "Vision Agent", "step": "Text extracted", "status": "success"})

                translation_result = translation_agent.analyze(
                    master_label_text=master_label,
                    foreign_text=extracted_text,
                    source_language=target_language,
                )
                agent_log.append({"agent": "Translation Agent", "step": "Semantic comparison complete", "status": "success"})

                layout_result = vision_agent.analyze_layout_compliance(file_b64, actual_file_type, target_language)
                agent_log.append({"agent": "Vision Agent", "step": "Layout analysis complete", "status": "success"})

                # ── Score ────────────────────────────────────────────────
                t_score = translation_result.get("semantic_score", 100)
                l_score = layout_result.get("layout_score", 100)
                overall = round((t_score * 0.6) + (l_score * 0.4), 1)

                if overall >= 90:
                    overall_status = "compliant"
                elif overall >= 70:
                    overall_status = "needs_review"
                else:
                    overall_status = "non_compliant"

                agent_log.append({"agent": "Orchestrator", "step": "Analysis complete", "status": "success"})

                # ── Persist result ───────────────────────────────────────
                result_obj = AnalysisResult(
                    job_id=uuid.UUID(job_id),
                    compliance_score=overall,
                    overall_status=overall_status,
                    translation_analysis=translation_result,
                    vision_analysis=layout_result,
                    agent_log=agent_log,
                    summary=(
                        f"Packaging review complete. Score: {overall}%. "
                        f"Translation: {t_score:.1f}%. Layout: {l_score:.1f}%."
                    ),
                )
                db.add(result_obj)

                job.status = "complete"
                job.workflow_state = "ai_reviewed"
                job.completed_at = datetime.now(timezone.utc)

                # Audit event
                db.add(AuditEvent(
                    job_id=uuid.UUID(job_id),
                    user_id=uuid.UUID(user_id) if user_id else None,
                    event_type="submitted",
                ))

                await db.commit()

            except Exception as exc:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                raise self.retry(exc=exc)

        await engine.dispose()

    asyncio.run(_run())
