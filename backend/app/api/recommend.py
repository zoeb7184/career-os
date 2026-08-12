"""
backend/app/api/recommend.py
─────────────────────────────
Job recommendation endpoints.

GET /api/v1/recommend/{user_id}  — Get personalised job recommendations
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import NotFoundError
from app.logger import get_logger

logger = get_logger("api_recommend")
router = APIRouter()


@router.get("/{user_id}", summary="Get personalised job recommendations")
async def recommend_jobs(
    user_id:     str,
    top_n:       int = Query(20, ge=1, le=50),
    country:     str | None = Query(None),
    remote_type: str | None = Query(None, description="remote | hybrid | onsite"),
    salary_min:  float | None = Query(None),
    db:          AsyncSession = Depends(get_db),
):
    """
    Get personalised job recommendations based on the user's resume.
    The user must have uploaded at least one resume first.
    """
    # Load user's resume
    result = await db.execute(
        text("SELECT raw_text FROM resumes WHERE user_id = :uid ORDER BY uploaded_at DESC LIMIT 1"),
        {"uid": user_id}
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("Resume for user", user_id)

    resume_text = row[0]

    # Load user's skills from their latest resume's extracted skills
    skills_result = await db.execute(
        text("""
            SELECT DISTINCT s.canonical_name
            FROM resumes r
            JOIN resume_skills rs ON rs.resume_id = r.id
            JOIN skills s ON rs.skill_id = s.id
            WHERE r.user_id = :uid
            ORDER BY s.canonical_name
            LIMIT 50
        """),
        {"uid": user_id}
    )
    user_skills = [r[0] for r in skills_result.fetchall()]

    # Run recommender
    try:
        from ml.recommender.recommender import JobRecommender
        rec = JobRecommender()
        result_obj = rec.recommend(
            resume_text = resume_text,
            user_skills = user_skills,
            user_id     = user_id,
            top_n       = top_n,
            country     = country,
            remote_type = remote_type,
            salary_min  = salary_min,
        )
    except Exception as exc:
        logger.error(f"Recommendation failed: {exc}", extra={"extra": {"user_id": user_id}})
        raise

    return JSONResponse(content={
        "data": {
            "user_id":          user_id,
            "total_candidates": result_obj.total_candidates,
            "returned":         len(result_obj.recommendations),
            "filters":          result_obj.applied_filters,
            "recommendations": [
                {
                    "job_id":        r.job_id,
                    "title":         r.title,
                    "company":       r.company,
                    "location":      r.location,
                    "remote_type":   r.remote_type,
                    "salary_min":    r.salary_min,
                    "salary_max":    r.salary_max,
                    "posted_at":     r.posted_at,
                    "url":           r.url,
                    "final_score":   r.final_score,
                    "matched_skills": r.matched_skills,
                }
                for r in result_obj.recommendations
            ],
        },
        "error": None,
    })
