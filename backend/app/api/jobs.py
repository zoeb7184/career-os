"""
backend/app/api/jobs.py
────────────────────────
Job listing endpoints.

GET /api/v1/jobs             — Search/list jobs with filters
GET /api/v1/jobs/{id}        — Single job detail
GET /api/v1/jobs/{id}/skills — Skills required for a job
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import NotFoundError
from app.logger import get_logger

logger = get_logger("api_jobs")
router = APIRouter()


@router.get("", summary="List and search jobs")
async def list_jobs(
    q:           str | None = Query(None, description="Keyword search in title + description"),
    country:     str | None = Query(None, description="Country code e.g. DE, GB"),
    remote_type: str | None = Query(None, description="remote | hybrid | onsite"),
    skill:       str | None = Query(None, description="Filter by required skill (canonical name)"),
    salary_min:  float | None = Query(None, description="Minimum salary"),
    page:        int = Query(1, ge=1),
    limit:       int = Query(20, ge=1, le=100),
    db:          AsyncSession = Depends(get_db),
):
    """
    List active jobs with optional filters.
    Results are sorted by posted date descending (newest first).
    """
    conditions  = ["j.is_active = TRUE"]
    params: dict = {"limit": limit, "offset": (page - 1) * limit}

    if q:
        conditions.append("(j.title ILIKE :q OR j.description ILIKE :q)")
        params["q"] = f"%{q}%"
    if country:
        conditions.append("j.country = :country")
        params["country"] = country.upper()
    if remote_type:
        conditions.append("j.remote_type = :remote_type")
        params["remote_type"] = remote_type
    if salary_min:
        conditions.append("j.salary_min >= :salary_min")
        params["salary_min"] = salary_min
    if skill:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM job_skills js
                JOIN skills s ON js.skill_id = s.id
                WHERE js.job_id = j.id AND s.canonical_name = :skill
            )
        """)
        params["skill"] = skill

    where = " AND ".join(conditions)

    # Count total for pagination
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM jobs j WHERE {where}"), params
    )
    total = count_result.scalar()

    # Fetch page
    result = await db.execute(
        text(f"""
            SELECT j.id, j.title, j.company, j.location, j.country,
                   j.remote_type, j.salary_min, j.salary_max,
                   j.posted_at, j.source
            FROM jobs j
            WHERE {where}
            ORDER BY j.posted_at DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """),
        params
    )
    rows = result.fetchall()

    return JSONResponse(content={
        "data": {
            "total": total,
            "page":  page,
            "limit": limit,
            "pages": max(1, -(-total // limit)),  # ceiling division
            "jobs":  [
                {
                    "id": r[0], "title": r[1], "company": r[2],
                    "location": r[3], "country": r[4], "remote_type": r[5],
                    "salary_min": float(r[6]) if r[6] is not None else None,
                    "salary_max": float(r[7]) if r[7] is not None else None,
                    "posted_at": r[8].isoformat() if r[8] else None,
                    "source": r[9],
                }
                for r in rows
            ],
        },
        "error": None,
    })


@router.get("/{job_id}", summary="Get a single job by ID")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Full detail for one job, including required skills."""
    result = await db.execute(
        text("""
            SELECT j.id, j.title, j.company, j.location, j.country,
                   j.remote_type, j.salary_min, j.salary_max,
                   j.description, j.posted_at, j.source, j.url
            FROM jobs j WHERE j.id = :id
        """),
        {"id": job_id}
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("Job", job_id)

    # Get skills
    skills_result = await db.execute(
        text("""
            SELECT s.canonical_name, js.skill_type
            FROM job_skills js
            JOIN skills s ON js.skill_id = s.id
            WHERE js.job_id = :job_id
            ORDER BY js.skill_type, s.canonical_name
        """),
        {"job_id": job_id}
    )
    skills = skills_result.fetchall()

    return JSONResponse(content={
        "data": {
            "id": row[0], "title": row[1], "company": row[2],
            "location": row[3], "country": row[4], "remote_type": row[5],
            "salary_min": float(row[6]) if row[6] is not None else None,
            "salary_max": float(row[7]) if row[7] is not None else None,
            "description": row[8],
            "posted_at": row[9].isoformat() if row[9] else None,
            "source": row[10], "url": row[11],
            "required_skills":  [s[0] for s in skills if s[1] == "required"],
            "preferred_skills": [s[0] for s in skills if s[1] == "preferred"],
        },
        "error": None,
    })
