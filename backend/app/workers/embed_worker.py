"""
backend/app/workers/embed_worker.py
────────────────────────────────────
Celery tasks for generating embeddings and upserting to Qdrant.
"""
import sys
sys.path.insert(0, '/pkgs')

from app.workers.celery_app import celery_app
from app.logger import get_logger

logger = get_logger("embed_worker")


@celery_app.task(bind=True, queue="embeddings", max_retries=3, name="embed_worker.embed_job")
def embed_job_task(self, job_id: str) -> dict:
    """Generate embedding for a job and upsert to Qdrant 'jobs' collection."""
    try:
        from sqlalchemy import text
        from app.config import settings
        from app.database import get_sync_engine
        from ml.shared.embedder import get_embedder

        engine = get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT title, company, description FROM jobs WHERE id = :id"
            ), {"id": job_id}).fetchone()

        if not row:
            logger.warning(f"Job not found: {job_id}")
            return {"status": "not_found", "job_id": job_id}

        title, company, description = row
        text_to_embed = f"{title} at {company or ''}. {description or ''}"

        embedder = get_embedder()
        vector = embedder.embed_chunks(text_to_embed)[0]

        # Upsert to Qdrant
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)

        # Get skills for payload
        with engine.connect() as conn:
            skills = [r[0] for r in conn.execute(text("""
                SELECT s.canonical_name FROM job_skills js
                JOIN skills s ON js.skill_id = s.id
                WHERE js.job_id = :jid
            """), {"jid": job_id}).fetchall()]

            # Get full job info for payload
            job_row = conn.execute(text("""
                SELECT title, company, location, country, remote_type,
                       salary_min, salary_max, posted_at, id
                FROM jobs WHERE id = :id
            """), {"id": job_id}).fetchone()

        payload = {
            "job_id": job_id,
            "title": job_row[0],
            "company": job_row[1],
            "location": job_row[2],
            "country": job_row[3],
            "remote_type": job_row[4],
            "salary_min": float(job_row[5]) if job_row[5] else None,
            "salary_max": float(job_row[6]) if job_row[6] else None,
            "posted_at": job_row[7].isoformat() if job_row[7] else None,
            "skills": skills,
        }

        client.upsert(
            collection_name="jobs",
            points=[PointStruct(id=job_id, vector=vector, payload=payload)]
        )

        # Update embedding_id in DB
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE jobs SET embedding_id = :eid WHERE id = :id"
            ), {"eid": job_id, "id": job_id})
            conn.commit()

        logger.info("Job embedded", extra={"extra": {"job_id": job_id}})
        return {"status": "ok", "job_id": job_id}

    except Exception as exc:
        logger.error(f"Embedding failed for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, queue="embeddings", max_retries=3, name="embed_worker.embed_resume")
def embed_resume_task(self, resume_id: str) -> dict:
    """Generate embedding for a resume and upsert to Qdrant 'resumes' collection."""
    try:
        from sqlalchemy import text
        from app.config import settings
        from app.database import get_sync_engine
        from ml.shared.embedder import get_embedder

        engine = get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT raw_text, user_id FROM resumes WHERE id = :id"
            ), {"id": resume_id}).fetchone()

        if not row:
            return {"status": "not_found", "resume_id": resume_id}

        raw_text, user_id = row
        embedder = get_embedder()
        vector = embedder.embed_chunks(raw_text or "")[0]

        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        client.upsert(
            collection_name="resumes",
            points=[PointStruct(
                id=resume_id,
                vector=vector,
                payload={"resume_id": resume_id, "user_id": user_id}
            )]
        )

        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE resumes SET embedding_id = :eid WHERE id = :id"
            ), {"eid": resume_id, "id": resume_id})
            conn.commit()

        logger.info("Resume embedded", extra={"extra": {"resume_id": resume_id}})
        return {"status": "ok", "resume_id": resume_id}

    except Exception as exc:
        logger.error(f"Resume embedding failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
