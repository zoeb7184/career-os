"""
backend/app/workers/ats_worker.py
──────────────────────────────────
Celery tasks for ATS analysis (runs async, off the main API thread).

These are stubs — they log and return a placeholder until
ml/ats_analyzer/ is built in Phase 2.
"""
from app.workers.celery_app import celery_app
from app.logger import get_logger

logger = get_logger("ats_worker")


@celery_app.task(bind=True, queue="ats", max_retries=3, name="ats_worker.analyze")
def analyze_resume_task(self, resume_id: str, job_id: str) -> dict:
    """
    Async ATS analysis task.
    Called by POST /api/v1/ats/analyze when analysis should run in background.

    Args:
        resume_id: UUID of the resume in the resumes table
        job_id:    UUID of the job in the jobs table

    Returns:
        dict with overall_score, breakdown, missing_skills, suggestions
    """
    logger.info(
        "ATS analysis task received",
        extra={"extra": {"resume_id": resume_id, "job_id": job_id, "task_id": self.request.id}}
    )

    # TODO Phase 2 Week 7: replace stub with real analysis
    # from ml.ats_analyzer.analyzer import ATSAnalyzer
    # analyzer = ATSAnalyzer()
    # return analyzer.analyze(resume_id=resume_id, job_id=job_id)

    logger.warning("ATS analyzer not yet built — returning stub result")
    return {
        "status":        "stub",
        "resume_id":     resume_id,
        "job_id":        job_id,
        "overall_score": None,
        "message":       "ATS analyzer not yet built — see Phase 2",
    }
