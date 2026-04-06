"""
Celery application configuration.

Broker and result backend: Redis
Workers pull jobs from the 'compliance' queue.

Start workers:
    celery -A tasks.celery_app worker --loglevel=info --concurrency=4 -Q compliance
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "pharma_guard",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.analysis_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,            # re-queue on worker crash
    worker_prefetch_multiplier=1,   # one task at a time per worker (long-running LLM calls)
    task_routes={
        "tasks.analysis_task.run_compliance_analysis": {"queue": "compliance"},
    },
    result_expires=86400,           # keep results for 24 hours
)
