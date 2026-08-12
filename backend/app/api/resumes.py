"""
backend/app/api/resumes.py
───────────────────────────
Resume upload and management.

POST /api/v1/resumes/upload  — upload PDF/DOCX, parse, store, queue embedding
GET  /api/v1/resumes/        — list user's resumes
DELETE /api/v1/resumes/{id}  — delete
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.api.auth import get_current_user
from app.errors import ValidationError, NotFoundError
from app.logger import get_logger

logger = get_logger("api_resumes")
router = APIRouter()
MAX_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise ValidationError(f"File too large. Max 5MB.")
    filename = file.filename or "resume.pdf"
    ext = filename.lower().split(".")[-1]
    if ext not in ("pdf", "docx", "doc"):
        raise ValidationError(f"Unsupported format: .{ext}")

    # Parse text
    try:
        from ml.ats_analyzer.analyzer import ResumeParser
        parser = ResumeParser()
        raw_text = parser.parse(file_bytes, filename)
    except Exception as exc:
        raise ValidationError(f"Could not parse file: {exc}")

    resume_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO resumes (id, user_id, filename, raw_text)
        VALUES (:id, :uid, :filename, :text)
    """), {"id": resume_id, "uid": current_user["id"], "filename": filename, "text": raw_text})
    await db.commit()

    # Queue embedding + skill extraction
    try:
        from app.workers.embed_worker import embed_resume_task
        embed_resume_task.delay(resume_id)
    except Exception as exc:
        logger.warning(f"Could not queue embedding: {exc}")
    try:
        from app.workers.skill_worker import extract_resume_skills_task
        extract_resume_skills_task.delay(resume_id)
    except Exception as exc:
        logger.warning(f"Could not queue skill extraction: {exc}")

    logger.info("Resume uploaded", extra={"extra": {"resume_id": resume_id, "user_id": current_user["id"]}})
    return JSONResponse(content={"data": {"resume_id": resume_id, "filename": filename, "text_length": len(raw_text)}, "error": None})


@router.get("/")
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT id, filename, uploaded_at FROM resumes
        WHERE user_id = :uid ORDER BY uploaded_at DESC
    """), {"uid": current_user["id"]})
    rows = result.fetchall()
    return JSONResponse(content={"data": [
        {"id": r[0], "filename": r[1], "uploaded_at": r[2].isoformat() if r[2] else None}
        for r in rows
    ], "error": None})


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text(
        "DELETE FROM resumes WHERE id = :id AND user_id = :uid RETURNING id"
    ), {"id": resume_id, "uid": current_user["id"]})
    if not result.fetchone():
        raise NotFoundError("Resume", resume_id)
    await db.commit()
    return JSONResponse(content={"data": {"deleted": resume_id}, "error": None})
