"""
backend/app/api/import_router.py
───────────────────────────────────
Smart Import — upload an .xlsx/.pdf application-tracker export, preview the
parsed + fuzzy-mapped rows (nothing is saved yet), then confirm to write the
(possibly user-edited) rows into `applications`.

Since `applications.job_id` is a required FK into `jobs`, each imported row
gets its own synthetic `jobs` row (source="import") to hang off of — the same
way a manually "saved" job does, just without a real listing behind it.

POST /api/v1/import/upload   — parse a file, return a preview
POST /api/v1/import/confirm  — save the previewed rows
GET  /api/v1/import/history  — list past imports for the current user
"""
import json
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.errors import NotFoundError, ValidationError
from app.logger import get_logger

logger = get_logger("api_import")
router = APIRouter()

MAX_SIZE = 10 * 1024 * 1024  # 10MB
VALID_STATUSES = {"saved", "applied", "interview", "offer", "rejected"}


class ImportRow(BaseModel):
    row_index: int = 0
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    date_applied: str | None = None       # ISO date "YYYY-MM-DD"
    status: str = "applied"
    job_url: str | None = None
    notes: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    platform: str | None = None
    is_duplicate: bool = False
    skip: bool = False                    # user excluded this row before confirming


class ConfirmImportRequest(BaseModel):
    filename: str
    file_type: str
    rows: list[ImportRow]


def _normalize_status(status: str | None) -> str:
    s = (status or "").strip().lower()
    return s if s in VALID_STATUSES else "saved"


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def _existing_applications(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    """The user's current tracker rows, used to flag duplicates in the preview."""
    result = await db.execute(text("""
        SELECT j.title, j.company, a.status
        FROM applications a
        LEFT JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = :uid
    """), {"uid": user_id})
    return [{"title": r[0], "company": r[1], "status": r[2]} for r in result.fetchall()]


@router.post("/upload")
async def upload_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationError("Uploaded file is empty.")
    if len(file_bytes) > MAX_SIZE:
        raise ValidationError("File too large. Max 10MB.")
    filename = file.filename or "import"

    # ml/ nodes aren't on sys.path by default outside the FastAPI process root —
    # same lazy-import pattern app/api/resumes.py uses for ml.ats_analyzer.
    from ml.import_parser.parser import preview_import

    existing = await _existing_applications(db, current_user["id"])
    result = preview_import(file_bytes, filename, existing_applications=existing)

    logger.info("Import file parsed", extra={"extra": {
        "user_id": current_user["id"], "filename": filename,
        "rows": result["summary"]["total"], "file_type": result["file_type"],
    }})
    return JSONResponse(content={"data": result, "error": None})


@router.post("/confirm")
async def confirm_import(
    request: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not request.rows:
        raise ValidationError("No rows to import.")

    import_id = str(uuid.uuid4())
    duplicate_count = sum(1 for r in request.rows if r.is_duplicate)

    # The imports row must exist before any application references it via
    # import_id (FK), so insert a placeholder now and fill in the real counts
    # once the loop below has computed them.
    await db.execute(text("""
        INSERT INTO imports (id, user_id, filename, file_type, total_rows, duplicate_count)
        VALUES (:id, :uid, :filename, :file_type, :total_rows, :duplicate_count)
    """), {
        "id": import_id, "uid": current_user["id"], "filename": request.filename,
        "file_type": request.file_type, "total_rows": len(request.rows),
        "duplicate_count": duplicate_count,
    })

    status_counts: dict[str, int] = {}
    imported = 0

    for row in request.rows:
        if row.skip:
            continue

        title = (row.job_title or "").strip() or "Untitled role"
        status = _normalize_status(row.status)
        applied_dt = _parse_iso_date(row.date_applied)

        job_id = str(uuid.uuid4())
        await db.execute(text("""
            INSERT INTO jobs (id, source, external_id, title, company, location,
                               salary_min, salary_max, url, posted_at, is_active)
            VALUES (:id, 'import', :ext_id, :title, :company, :location,
                    :salary_min, :salary_max, :url, :posted_at, true)
        """), {
            "id": job_id, "ext_id": job_id, "title": title,
            "company": row.company, "location": row.location,
            "salary_min": row.salary_min, "salary_max": row.salary_max,
            "url": row.job_url,
            "posted_at": datetime.combine(applied_dt, datetime.min.time()) if applied_dt else None,
        })

        app_id = str(uuid.uuid4())
        await db.execute(text("""
            INSERT INTO applications (id, user_id, job_id, status, notes,
                                       applied_at, platform, import_id)
            VALUES (:id, :uid, :jid, :status, :notes, :applied_at, :platform, :import_id)
        """), {
            "id": app_id, "uid": current_user["id"], "jid": job_id,
            "status": status, "notes": row.notes, "applied_at": applied_dt,
            "platform": row.platform, "import_id": import_id,
        })

        status_counts[status] = status_counts.get(status, 0) + 1
        imported += 1

    skipped = len(request.rows) - imported

    await db.execute(text("""
        UPDATE imports
        SET imported_rows = :imported_rows, skipped_rows = :skipped_rows,
            status_counts = CAST(:status_counts AS JSON)
        WHERE id = :id
    """), {
        "id": import_id, "imported_rows": imported, "skipped_rows": skipped,
        "status_counts": json.dumps(status_counts),
    })
    await db.commit()

    logger.info("Import confirmed", extra={"extra": {
        "user_id": current_user["id"], "import_id": import_id,
        "imported": imported, "skipped": skipped,
    }})
    return JSONResponse(content={"data": {
        "import_id": import_id,
        "imported": imported,
        "skipped": skipped,
        "duplicate_count": duplicate_count,
        "status_counts": status_counts,
    }, "error": None})


@router.get("/history")
async def import_history(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT id, filename, file_type, total_rows, imported_rows,
               skipped_rows, duplicate_count, status_counts, created_at
        FROM imports
        WHERE user_id = :uid
        ORDER BY created_at DESC
    """), {"uid": current_user["id"]})
    rows = result.fetchall()
    return JSONResponse(content={"data": [
        {
            "id": r[0], "filename": r[1], "file_type": r[2],
            "total_rows": r[3], "imported_rows": r[4], "skipped_rows": r[5],
            "duplicate_count": r[6], "status_counts": r[7] or {},
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ], "error": None})


@router.delete("/history/{import_id}")
async def delete_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deletes an import batch AND everything it created: the applications it
    inserted, and the synthetic `jobs` rows those applications hung off of
    (never a real ingested listing — always source='import', scoped to job_ids
    this import's own applications pointed at)."""
    owned = await db.execute(text(
        "SELECT id FROM imports WHERE id = :id AND user_id = :uid"
    ), {"id": import_id, "uid": current_user["id"]})
    if not owned.fetchone():
        raise NotFoundError("Import", import_id)

    job_ids_result = await db.execute(text(
        "SELECT job_id FROM applications WHERE import_id = :id AND user_id = :uid"
    ), {"id": import_id, "uid": current_user["id"]})
    job_ids = [r[0] for r in job_ids_result.fetchall()]

    deleted_apps = await db.execute(text(
        "DELETE FROM applications WHERE import_id = :id AND user_id = :uid RETURNING id"
    ), {"id": import_id, "uid": current_user["id"]})
    deleted_count = len(deleted_apps.fetchall())

    if job_ids:
        await db.execute(text(
            "DELETE FROM jobs WHERE id = ANY(:job_ids) AND source = 'import'"
        ), {"job_ids": job_ids})

    await db.execute(text(
        "DELETE FROM imports WHERE id = :id AND user_id = :uid"
    ), {"id": import_id, "uid": current_user["id"]})
    await db.commit()

    logger.info("Import deleted", extra={"extra": {
        "user_id": current_user["id"], "import_id": import_id, "applications_removed": deleted_count,
    }})
    return JSONResponse(content={"data": {"deleted": import_id, "applications_removed": deleted_count}, "error": None})
