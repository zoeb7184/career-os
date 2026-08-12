"""
backend/app/api/applications.py
────────────────────────────────
Application tracker (Kanban board data).

POST   /api/v1/applications/        — save a job
GET    /api/v1/applications/        — list all applications
PATCH  /api/v1/applications/{id}    — update status
DELETE /api/v1/applications/{id}    — remove
"""
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.api.auth import get_current_user
from app.errors import NotFoundError, ValidationError
from app.logger import get_logger

logger = get_logger("api_applications")
router = APIRouter()

VALID_STATUSES = {"saved", "applied", "interview", "offer", "rejected"}


class SaveJobRequest(BaseModel):
    job_id: str
    notes: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str
    notes: str | None = None


@router.post("/")
async def save_job(
    request: SaveJobRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    app_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO applications (id, user_id, job_id, status, notes)
        VALUES (:id, :uid, :jid, 'saved', :notes)
        ON CONFLICT DO NOTHING
    """), {"id": app_id, "uid": current_user["id"], "jid": request.job_id, "notes": request.notes})
    await db.commit()
    return JSONResponse(content={"data": {"application_id": app_id, "status": "saved"}, "error": None})


@router.get("/")
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT a.id, a.job_id, a.status, a.ats_score, a.notes,
               a.created_at, a.updated_at,
               j.title, j.company, j.location, j.remote_type
        FROM applications a
        LEFT JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = :uid
        ORDER BY a.updated_at DESC
    """), {"uid": current_user["id"]})
    rows = result.fetchall()
    return JSONResponse(content={"data": [
        {
            "id": r[0], "job_id": r[1], "status": r[2], "ats_score": r[3],
            "notes": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "updated_at": r[6].isoformat() if r[6] else None,
            "job": {"title": r[7], "company": r[8], "location": r[9], "remote_type": r[10]},
        }
        for r in rows
    ], "error": None})


@router.patch("/{app_id}")
async def update_status(
    app_id: str,
    request: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if request.status not in VALID_STATUSES:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
    result = await db.execute(text("""
        UPDATE applications SET status = :status, notes = COALESCE(:notes, notes), updated_at = NOW()
        WHERE id = :id AND user_id = :uid RETURNING id
    """), {"status": request.status, "notes": request.notes, "id": app_id, "uid": current_user["id"]})
    if not result.fetchone():
        raise NotFoundError("Application", app_id)
    await db.commit()
    return JSONResponse(content={"data": {"id": app_id, "status": request.status}, "error": None})


@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text(
        "DELETE FROM applications WHERE id = :id AND user_id = :uid RETURNING id"
    ), {"id": app_id, "uid": current_user["id"]})
    if not result.fetchone():
        raise NotFoundError("Application", app_id)
    await db.commit()
    return JSONResponse(content={"data": {"deleted": app_id}, "error": None})
