"""
data-pipeline/flows/snapshot_flow.py
──────────────────────────────────────
Daily market snapshot flow — records skill demand counts for forecasting.
Run after ingestion_flow completes.

Schedule: daily at 03:00 UTC (after ingestion at 02:00)
"""
import uuid
from datetime import datetime, timezone, date
from prefect import flow, task
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/pkgs')


@task(name="create-skill-snapshots")
def create_snapshots() -> dict:
    from sqlalchemy import text
    from app.database import get_sync_engine

    engine = get_sync_engine()
    today = date.today()
    inserted = 0

    with engine.connect() as conn:
        # Get demand per skill per country
        rows = conn.execute(text("""
            SELECT js.skill_id, j.country, COUNT(DISTINCT j.id) as demand,
                   AVG(j.salary_max) as avg_salary
            FROM job_skills js
            JOIN jobs j ON js.job_id = j.id
            WHERE j.is_active = TRUE
            GROUP BY js.skill_id, j.country
        """)).fetchall()

        for row in rows:
            skill_id, country, demand, avg_salary = row
            try:
                conn.execute(text("""
                    INSERT INTO market_snapshots (id, snapshot_date, skill_id, country, demand, avg_salary)
                    VALUES (:id, :date, :skill_id, :country, :demand, :avg_salary)
                    ON CONFLICT (snapshot_date, skill_id, country) DO UPDATE
                    SET demand = EXCLUDED.demand, avg_salary = EXCLUDED.avg_salary
                """), {
                    "id": str(uuid.uuid4()),
                    "date": today,
                    "skill_id": skill_id,
                    "country": country,
                    "demand": demand,
                    "avg_salary": float(avg_salary) if avg_salary else None,
                })
                inserted += 1
            except Exception as exc:
                print(f"Snapshot insert failed: {exc}")

        conn.commit()

    return {"date": str(today), "snapshots_created": inserted}


@flow(name="daily-market-snapshot")
def daily_market_snapshot():
    result = create_snapshots()
    print(f"✅ Market snapshot complete: {result}")
    return result


if __name__ == "__main__":
    daily_market_snapshot()
