"""
backend/app/workers/celery_app.py
──────────────────────────────────
Celery instance shared by all worker tasks.

Queues:
    ats       — ATS analysis tasks (CPU-heavy, 2 workers)
    embeddings — embedding generation tasks (model-heavy, 1 worker)
    default   — everything else

Usage in task files:
    from app.workers.celery_app import celery_app

    @celery_app.task(bind=True, queue="ats", max_retries=3)
    def analyze_resume_task(self, resume_id: str, job_id: str):
        ...
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "career_os",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.ats_worker",
        "app.workers.embed_worker",
        "app.workers.skill_worker",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,         # only ack after task completes (safer)
    worker_prefetch_multiplier=1, # one task at a time per worker (fair)
    task_routes={
        "app.workers.ats_worker.*":   {"queue": "ats"},
        "app.workers.embed_worker.*": {"queue": "embeddings"},
    },
    task_soft_time_limit=120,     # warn after 2 min
    task_time_limit=180,          # kill after 3 min
)
