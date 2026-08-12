"""
backend/app/api/ats.py
───────────────────────
ATS Resume Analyzer API endpoints.

POST /api/v1/ats/analyze
  Upload a resume file + provide a job_id → get ATS score back.

GET /api/v1/ats/result/{task_id}
  Poll for async ATS result (for large files).
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.database import get_db
from app.errors import NotFoundError, ValidationError
from app.logger import get_logger

logger = get_logger("api_ats")
router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class ATSResponse(BaseModel):
    overall_score:   float
    breakdown:       dict
    missing_skills:  list[str]
    matched_skills:  list[str]
    suggestions:     list[str]
    processing_ms:   int
    resume_id:       str | None
    job_id:          str | None


@router.post("/analyze", summary="Analyse resume against a job description")
async def analyze_resume(
    file:   UploadFile = File(..., description="Resume file — PDF or DOCX, max 5MB"),
    job_id: str        = Form(..., description="UUID of the job to compare against"),
    db:     AsyncSession = Depends(get_db),
):
    """
    Upload a resume and get an ATS score against a specific job.

    The response includes:
    - overall_score (0-100)
    - breakdown by component (skill_match, embedding_sim, structural, keyword)
    - missing_skills: what required skills are absent from the resume
    - suggestions: specific actionable improvements
    """
    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValidationError(f"File too large. Max size is 5MB, got {len(file_bytes)/1024/1024:.1f}MB")

    # Validate file type
    filename = file.filename or "resume.pdf"
    ext = filename.lower().split(".")[-1]
    if ext not in ("pdf", "docx", "doc"):
        raise ValidationError(f"Unsupported file type: .{ext}. Please upload PDF or DOCX.")

    # Load job from DB
    result = await db.execute(
        text("SELECT id, title, description FROM jobs WHERE id = :job_id"),
        {"job_id": job_id}
    )
    job_row = result.fetchone()
    if not job_row:
        raise NotFoundError("Job", job_id)

    job_db_id, job_title, job_description = job_row

    # Load required skills for this job
    skills_result = await db.execute(
        text("""
            SELECT s.canonical_name
            FROM job_skills js
            JOIN skills s ON js.skill_id = s.id
            WHERE js.job_id = :job_id AND js.skill_type = 'required'
        """),
        {"job_id": job_id}
    )
    required_skills = [row[0] for row in skills_result.fetchall()]

    # Run ATS analysis
    try:
        from ml.ats_analyzer.analyzer import ATSAnalyzer
        analyzer  = ATSAnalyzer()
        resume_id = str(uuid.uuid4())
        ats_result = analyzer.analyze_from_file(
            file_bytes      = file_bytes,
            filename        = filename,
            job_description = job_description or "",
            required_skills = required_skills,
            job_title       = job_title or "",
            resume_id       = resume_id,
            job_id          = job_id,
        )
    except Exception as exc:
        logger.error(f"ATS analysis failed: {exc}", extra={"extra": {"job_id": job_id}})
        raise

    return JSONResponse(content={
        "data": {
            "overall_score":  ats_result.overall_score,
            "breakdown": {
                "skill_match":   ats_result.breakdown.skill_match,
                "embedding_sim": ats_result.breakdown.embedding_sim,
                "structural":    ats_result.breakdown.structural,
                "keyword":       ats_result.breakdown.keyword,
            },
            "missing_skills": ats_result.missing_skills,
            "matched_skills": ats_result.matched_skills,
            "suggestions":    ats_result.suggestions,
            "processing_ms":  ats_result.processing_ms,
            "resume_id":      ats_result.resume_id,
            "job_id":         ats_result.job_id,
        },
        "error": None,
    })
