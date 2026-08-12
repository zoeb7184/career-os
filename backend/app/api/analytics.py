"""
backend/app/api/analytics.py
──────────────────────────────
Market Intelligence Dashboard endpoints.
Powers the charts and statistics on the analytics page.

GET /api/v1/analytics/skills/top         — Top N skills by job demand
GET /api/v1/analytics/skills/trending    — Fastest growing skills
GET /api/v1/analytics/salary             — Salary ranges by skill/role
GET /api/v1/analytics/remote             — Remote vs hybrid vs onsite breakdown
GET /api/v1/analytics/companies/top      — Top hiring companies
GET /api/v1/analytics/locations/top      — Top hiring cities/countries
GET /api/v1/analytics/forecast/{skill}   — 90-day demand forecast for a skill
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logger import get_logger

logger = get_logger("api_analytics")
router = APIRouter()


@router.get("/skills/top", summary="Top skills by job demand")
async def top_skills(
    limit:   int = Query(20, ge=1, le=100, description="Number of skills to return"),
    country: str | None = Query(None, description="Filter by country code e.g. DE"),
    db:      AsyncSession = Depends(get_db),
):
    """Top N skills ranked by number of job postings that require them."""
    country_filter = "AND j.country = :country" if country else ""
    result = await db.execute(
        text(f"""
            SELECT
                s.canonical_name AS skill,
                s.category,
                COUNT(DISTINCT js.job_id) AS job_count,
                ROUND(AVG(j.salary_max)::numeric, 0) AS avg_salary_max
            FROM job_skills js
            JOIN skills s ON js.skill_id = s.id
            JOIN jobs j ON js.job_id = j.id
            WHERE j.is_active = TRUE
              AND js.skill_type = 'required'
              {country_filter}
            GROUP BY s.canonical_name, s.category
            ORDER BY job_count DESC
            LIMIT :limit
        """),
        {"limit": limit, "country": country}
    )
    rows = result.fetchall()
    return JSONResponse(content={
        "data": [
            {"skill": r[0], "category": r[1], "job_count": r[2],
             "avg_salary_max": float(r[3]) if r[3] is not None else None}
            for r in rows
        ],
        "error": None,
    })


@router.get("/remote", summary="Remote vs hybrid vs onsite breakdown")
async def remote_breakdown(
    country: str | None = Query(None),
    db:      AsyncSession = Depends(get_db),
):
    """Percentage breakdown of remote work types across active jobs."""
    country_filter = "AND country = :country" if country else ""
    result = await db.execute(
        text(f"""
            SELECT
                COALESCE(remote_type, 'unknown') AS remote_type,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
            FROM jobs
            WHERE is_active = TRUE {country_filter}
            GROUP BY remote_type
            ORDER BY count DESC
        """),
        {"country": country}
    )
    rows = result.fetchall()
    return JSONResponse(content={
        "data":  [{"remote_type": r[0], "count": r[1], "percentage": float(r[2])} for r in rows],
        "error": None,
    })


@router.get("/companies/top", summary="Top hiring companies")
async def top_companies(
    limit:   int = Query(15, ge=1, le=50),
    country: str | None = Query(None),
    db:      AsyncSession = Depends(get_db),
):
    """Companies with the most active job listings."""
    country_filter = "AND country = :country" if country else ""
    result = await db.execute(
        text(f"""
            SELECT
                company,
                COUNT(*) AS open_roles,
                ROUND(AVG(salary_max)::numeric, 0) AS avg_salary
            FROM jobs
            WHERE is_active = TRUE
              AND company IS NOT NULL
              {country_filter}
            GROUP BY company
            ORDER BY open_roles DESC
            LIMIT :limit
        """),
        {"limit": limit, "country": country}
    )
    rows = result.fetchall()
    return JSONResponse(content={
        "data":  [{"company": r[0], "open_roles": r[1],
                    "avg_salary": float(r[2]) if r[2] is not None else None} for r in rows],
        "error": None,
    })


@router.get("/locations/top", summary="Top hiring locations")
async def top_locations(
    limit: int = Query(15, ge=1, le=50),
    db:    AsyncSession = Depends(get_db),
):
    """Cities/regions with most active job listings."""
    result = await db.execute(
        text("""
            SELECT
                location,
                country,
                COUNT(*) AS job_count
            FROM jobs
            WHERE is_active = TRUE
              AND location IS NOT NULL
            GROUP BY location, country
            ORDER BY job_count DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    rows = result.fetchall()
    return JSONResponse(content={
        "data":  [{"location": r[0], "country": r[1], "job_count": r[2]} for r in rows],
        "error": None,
    })


@router.get("/salary", summary="Salary ranges by skill")
async def salary_by_skill(
    skill:   str = Query(..., description="Canonical skill name e.g. Python"),
    country: str | None = Query(None),
    db:      AsyncSession = Depends(get_db),
):
    """Min, median, and max salary for jobs requiring a specific skill."""
    country_filter = "AND j.country = :country" if country else ""
    result = await db.execute(
        text(f"""
            SELECT
                ROUND(MIN(j.salary_min)::numeric, 0)    AS salary_min,
                ROUND(AVG(j.salary_max)::numeric, 0)    AS salary_avg,
                ROUND(MAX(j.salary_max)::numeric, 0)    AS salary_max,
                COUNT(DISTINCT j.id)                     AS job_count
            FROM jobs j
            JOIN job_skills js ON js.job_id = j.id
            JOIN skills s ON js.skill_id = s.id
            WHERE j.is_active = TRUE
              AND s.canonical_name = :skill
              AND j.salary_min IS NOT NULL
              {country_filter}
        """),
        {"skill": skill, "country": country}
    )
    row = result.fetchone()
    if not row or not row[3]:
        return JSONResponse(content={"data": None, "error": {"code": "ANA_404",
            "message": f"No salary data found for skill: {skill}", "detail": {}}})

    return JSONResponse(content={
        "data": {
            "skill":      skill,
            "salary_min": float(row[0]) if row[0] is not None else None,
            "salary_avg": float(row[1]) if row[1] is not None else None,
            "salary_max": float(row[2]) if row[2] is not None else None,
            "job_count":  row[3],
            "country":    country,
        },
        "error": None,
    })


@router.get("/forecast/{skill}", summary="90-day demand forecast for a skill")
async def forecast_skill(skill: str, db: AsyncSession = Depends(get_db)):
    """
    Prophet-based 30/60/90-day demand forecast for one skill, built from
    market_snapshots history. Needs >= 30 days of daily snapshots (run
    `make snapshot` daily) — until then this returns data: null rather
    than a hard error, since "not enough history yet" is expected on a
    freshly-seeded install, not a failure.
    """
    import pandas as pd
    from ml.forecaster.forecaster import ForecasterError, SkillDemandForecaster

    result = await db.execute(text("""
        SELECT ms.snapshot_date AS ds, SUM(ms.demand) AS y
        FROM market_snapshots ms
        JOIN skills s ON ms.skill_id = s.id
        WHERE s.canonical_name = :skill
        GROUP BY ms.snapshot_date
        ORDER BY ms.snapshot_date
    """), {"skill": skill})
    rows = result.fetchall()

    if not rows:
        return JSONResponse(content={"data": None, "error": {
            "code": "ANA_405", "message": f"No market snapshot history yet for skill: {skill}", "detail": {}
        }})

    df = pd.DataFrame(rows, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)

    try:
        forecast = SkillDemandForecaster().forecast_skill(skill, df)
    except ForecasterError as exc:
        return JSONResponse(content={"data": None, "error": {
            "code": exc.code, "message": exc.message, "detail": exc.detail
        }})

    return JSONResponse(content={
        "data": {
            "skill_name":      forecast.skill_name,
            "current_demand":  forecast.current_demand,
            "forecast_30d":    forecast.forecast_30d,
            "forecast_60d":    forecast.forecast_60d,
            "forecast_90d":    forecast.forecast_90d,
            "trend":           forecast.trend,
            "confidence_low":  forecast.confidence_low,
            "confidence_high": forecast.confidence_high,
            "data_points":     forecast.data_points,
        },
        "error": None,
    })


@router.get("/summary", summary="Dashboard summary stats")
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    """High-level numbers for the analytics dashboard header."""
    result = await db.execute(text("""
        SELECT
            COUNT(*)                                           AS total_active_jobs,
            COUNT(DISTINCT company)                           AS total_companies,
            COUNT(DISTINCT country)                           AS total_countries,
            COUNT(CASE WHEN remote_type = 'remote' THEN 1 END) AS remote_jobs,
            COUNT(CASE WHEN ingested_at > NOW() - INTERVAL '24 hours' THEN 1 END) AS new_today
        FROM jobs
        WHERE is_active = TRUE
    """))
    row = result.fetchone()
    return JSONResponse(content={
        "data": {
            "total_active_jobs": row[0],
            "total_companies":   row[1],
            "total_countries":   row[2],
            "remote_jobs":       row[3],
            "new_today":         row[4],
        },
        "error": None,
    })
