"""
backend/app/workers/skill_worker.py
─────────────────────────────────────
Celery task: extract structured skills from a job description via the LLM
skill_extractor node, normalise them against the skills taxonomy, and link
them into the job_skills table.

Queued once per new job from data_pipeline.flows.ingestion_flow, right
alongside the embedding task. Without this, job_skills stays empty and the
recommender / ATS analyzer / analytics endpoints have nothing to match on.
"""
import asyncio

from app.workers.celery_app import celery_app
from app.logger import get_logger

logger = get_logger("skill_worker")


@celery_app.task(bind=True, queue="default", max_retries=3, name="skill_worker.extract_job_skills")
def extract_job_skills_task(self, job_id: str) -> dict:
    """Extract skills for one job via the LLM, normalise, and upsert into job_skills."""
    try:
        from sqlalchemy import text
        from app.database import get_sync_engine
        from ml.skill_extractor.extractor import SkillExtractor
        from data_pipeline.transformers.skill_normalizer import normalise_skill

        engine = get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT description FROM jobs WHERE id = :id"
            ), {"id": job_id}).fetchone()

        if not row:
            logger.warning(f"Job not found: {job_id}")
            return {"status": "not_found", "job_id": job_id}

        description = row[0] or ""
        extractor = SkillExtractor()
        extracted = asyncio.run(extractor.extract(description, job_id))

        # Normalise raw LLM skill strings against the canonical taxonomy,
        # de-duplicating (required wins over preferred if a skill appears in both).
        linked: dict[str, tuple[str, float]] = {}
        for raw in extracted.preferred_skills:
            canon = normalise_skill(raw)
            if canon:
                linked[canon] = ("preferred", 0.5)
        for raw in extracted.required_skills:
            canon = normalise_skill(raw)
            if canon:
                linked[canon] = ("required", 1.0)

        upserted = 0
        with engine.connect() as conn:
            for canon, (skill_type, importance) in linked.items():
                skill_row = conn.execute(text(
                    "SELECT id FROM skills WHERE canonical_name = :name"
                ), {"name": canon}).fetchone()
                if not skill_row:
                    continue
                conn.execute(text("""
                    INSERT INTO job_skills (job_id, skill_id, skill_type, importance)
                    VALUES (:job_id, :skill_id, :skill_type, :importance)
                    ON CONFLICT (job_id, skill_id) DO UPDATE
                    SET skill_type = EXCLUDED.skill_type, importance = EXCLUDED.importance
                """), {
                    "job_id": job_id, "skill_id": skill_row[0],
                    "skill_type": skill_type, "importance": importance,
                })
                upserted += 1
            conn.commit()

        logger.info("Job skills linked", extra={"extra": {"job_id": job_id, "skills_linked": upserted}})
        return {"status": "ok", "job_id": job_id, "skills_linked": upserted}

    except Exception as exc:
        logger.error(f"Skill extraction failed for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, queue="default", max_retries=3, name="skill_worker.extract_resume_skills")
def extract_resume_skills_task(self, resume_id: str) -> dict:
    """Extract skills from an uploaded resume's raw text, normalise, and upsert into resume_skills.

    Feeds GET /api/v1/recommend/{user_id}, which re-ranks candidate jobs by
    skill overlap against resume_skills.
    """
    try:
        from sqlalchemy import text
        from app.database import get_sync_engine
        from ml.skill_extractor.extractor import SkillExtractor
        from data_pipeline.transformers.skill_normalizer import normalise_skill

        engine = get_sync_engine()
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT raw_text FROM resumes WHERE id = :id"
            ), {"id": resume_id}).fetchone()

        if not row:
            logger.warning(f"Resume not found: {resume_id}")
            return {"status": "not_found", "resume_id": resume_id}

        raw_text = row[0] or ""
        extractor = SkillExtractor()
        # A resume isn't a job posting, but the same "required vs preferred" extraction
        # prompt still pulls out the skills/tools/technologies mentioned in it.
        extracted = asyncio.run(extractor.extract(raw_text, resume_id))

        canonical_skills: set[str] = set()
        for raw in (*extracted.required_skills, *extracted.preferred_skills, *extracted.technologies):
            canon = normalise_skill(raw)
            if canon:
                canonical_skills.add(canon)

        upserted = 0
        with engine.connect() as conn:
            for canon in canonical_skills:
                skill_row = conn.execute(text(
                    "SELECT id FROM skills WHERE canonical_name = :name"
                ), {"name": canon}).fetchone()
                if not skill_row:
                    continue
                conn.execute(text("""
                    INSERT INTO resume_skills (resume_id, skill_id, importance)
                    VALUES (:resume_id, :skill_id, 1.0)
                    ON CONFLICT (resume_id, skill_id) DO NOTHING
                """), {"resume_id": resume_id, "skill_id": skill_row[0]})
                upserted += 1
            conn.commit()

        logger.info("Resume skills linked", extra={"extra": {"resume_id": resume_id, "skills_linked": upserted}})
        return {"status": "ok", "resume_id": resume_id, "skills_linked": upserted}

    except Exception as exc:
        logger.error(f"Resume skill extraction failed for {resume_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
