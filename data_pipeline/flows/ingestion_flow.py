"""
data-pipeline/flows/ingestion_flow.py
───────────────────────────────────────
Prefect flow: daily job ingestion from all sources.

Schedule: daily at 02:00 UTC (configured in Prefect Cloud UI or via deployment.yaml)

What this does:
  1. Fetch jobs from all connectors (Adzuna, Reed, Remotive)
  2. Deduplicate against existing DB records
  3. Normalise skill strings
  4. Upsert new jobs to PostgreSQL
  5. Queue embedding tasks for new jobs (Celery)
  6. Mark stale jobs as inactive

Run manually:
    python -m data_pipeline.flows.ingestion_flow

Deploy to Prefect Cloud:
    prefect deploy data_pipeline/flows/ingestion_flow.py:ingest_all_jobs \
      --name "daily-job-ingestion" --cron "0 2 * * *"
"""
from __future__ import annotations
import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

# Prefect
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.config import settings
from data_pipeline.connectors.base import RawJob
from data_pipeline.connectors.adzuna import AdzunaConnector
from data_pipeline.connectors.reed import ReedConnector
from data_pipeline.connectors.remotive import RemotiveConnector
from data_pipeline.transformers.dedup import deduplicate_batch, compute_hash
from data_pipeline.transformers.skill_normalizer import normalise_skill

logger = get_logger("ingestion_flow")


# ── Tasks ──────────────────────────────────────────────────────────

@task(name="fetch-adzuna", retries=2, retry_delay_seconds=60,
      cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=6))
async def fetch_adzuna(country: str = "de") -> list[RawJob]:
    connector = AdzunaConnector()
    return await connector.fetch(country=country, max_pages=10)


@task(name="fetch-reed", retries=2, retry_delay_seconds=60)
async def fetch_reed() -> list[RawJob]:
    connector = ReedConnector()
    return await connector.fetch(country="gb", max_pages=5)


@task(name="fetch-remotive", retries=2, retry_delay_seconds=60)
async def fetch_remotive() -> list[RawJob]:
    connector = RemotiveConnector()
    return await connector.fetch(country="global")


@task(name="load-existing-ids")
def load_existing_ids() -> tuple[set[str], set[tuple[str, str]]]:
    """Load existing hashes and (source, external_id) pairs from DB for dedup."""
    from sqlalchemy import text
    from app.database import get_sync_engine
    engine = get_sync_engine()
    with engine.connect() as conn:
        hashes = {row[0] for row in conn.execute(
            text("SELECT description_hash FROM jobs WHERE description_hash IS NOT NULL")
        )}
        ids = {(row[0], row[1]) for row in conn.execute(
            text("SELECT source, external_id FROM jobs")
        )}
    logger.info(f"Loaded {len(ids):,} existing job IDs from DB")
    return hashes, ids


@task(name="upsert-jobs")
def upsert_jobs(jobs: list[RawJob]) -> dict[str, int]:
    """
    Insert new jobs into PostgreSQL.
    Returns counts: {inserted, failed}
    """
    from sqlalchemy.orm import Session
    from app.database import get_sync_engine
    from app.models.job import Job

    engine = get_sync_engine()
    inserted = 0
    failed   = 0

    with Session(engine) as session:
        for raw in jobs:
            try:
                desc_hash = compute_hash(raw.description)
                job = Job(
                    id               = str(uuid.uuid4()),
                    source           = raw.source,
                    external_id      = raw.external_id,
                    title            = raw.title,
                    company          = raw.company,
                    location         = raw.location,
                    country          = raw.country,
                    remote_type      = raw.remote_type,
                    salary_min       = raw.salary_min,
                    salary_max       = raw.salary_max,
                    description      = raw.description,
                    url              = raw.url,
                    description_hash = desc_hash,
                    posted_at        = raw.posted_at,
                    is_active        = True,
                    ingested_at      = datetime.now(timezone.utc),
                )
                session.add(job)
                inserted += 1

                # Batch commit every 500 records
                if inserted % 500 == 0:
                    session.commit()
                    logger.info(f"Committed batch: {inserted} jobs so far")

            except Exception as exc:
                session.rollback()
                failed += 1
                logger.error(
                    f"Failed to insert job",
                    extra={"extra": {"source": raw.source, "external_id": raw.external_id, "error": str(exc)}}
                )

        session.commit()

    logger.info("Upsert complete", extra={"extra": {"inserted": inserted, "failed": failed}})
    return {"inserted": inserted, "failed": failed}


@task(name="mark-expired-jobs")
def mark_expired_jobs(active_external_ids: dict[str, list[str]]) -> int:
    """
    Mark jobs as inactive if they were not returned in the latest fetch.
    Only marks jobs older than 7 days (fresh jobs may not have appeared in all pages).

    Args:
        active_external_ids: {source: [external_id, ...]} from latest fetch.

    Returns:
        Count of jobs marked inactive.
    """
    from sqlalchemy import text
    from app.database import get_sync_engine
    engine = get_sync_engine()
    total_expired = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    with engine.connect() as conn:
        for source, ids in active_external_ids.items():
            if not ids:
                continue
            # Mark jobs from this source that are NOT in the current fetch AND older than 7 days
            result = conn.execute(text("""
                UPDATE jobs
                SET is_active = FALSE
                WHERE source = :source
                  AND external_id NOT IN :ids
                  AND ingested_at < :cutoff
                  AND is_active = TRUE
            """), {"source": source, "ids": tuple(ids) or ("__none__",), "cutoff": cutoff})
            expired = result.rowcount
            total_expired += expired
            if expired:
                logger.info(f"Marked {expired} {source} jobs as expired")
        conn.commit()

    return total_expired


@task(name="queue-embeddings")
def queue_embedding_tasks(job_ids: list[str]) -> int:
    """Queue Celery embedding tasks for all new jobs."""
    from app.workers.embed_worker import embed_job_task
    queued = 0
    for job_id in job_ids:
        embed_job_task.delay(job_id)
        queued += 1
    logger.info(f"Queued {queued} embedding tasks")
    return queued


@task(name="queue-skill-extraction")
def queue_skill_extraction_tasks(job_ids: list[str]) -> int:
    """Queue Celery skill-extraction tasks (LLM) for all new jobs."""
    from app.workers.skill_worker import extract_job_skills_task
    queued = 0
    for job_id in job_ids:
        extract_job_skills_task.delay(job_id)
        queued += 1
    logger.info(f"Queued {queued} skill extraction tasks")
    return queued


# ── Main flow ──────────────────────────────────────────────────────

@flow(name="ingest-all-jobs", log_prints=True)
async def ingest_all_jobs():
    """
    Master ingestion flow.
    Runs daily. Fetches → deduplicates → normalises → upserts → queues embeddings.
    """
    flow_start = datetime.now(timezone.utc)
    logger.info("Ingestion flow started", extra={"extra": {"started_at": flow_start.isoformat()}})

    # 1. Fetch from all sources in parallel
    # Note: async tasks return a coroutine from .submit() in this Prefect version —
    # it must be awaited to get the PrefectFuture before calling .result() on it.
    adzuna_future  = await fetch_adzuna.submit("de")
    reed_future    = await fetch_reed.submit()
    remotive_future = await fetch_remotive.submit()

    adzuna_jobs  = await adzuna_future.result()
    reed_jobs    = await reed_future.result()
    remotive_jobs = await remotive_future.result()

    all_raw: list[RawJob] = adzuna_jobs + reed_jobs + remotive_jobs
    logger.info(f"Total raw jobs fetched: {len(all_raw)}", extra={"extra": {
        "adzuna": len(adzuna_jobs), "reed": len(reed_jobs), "remotive": len(remotive_jobs)
    }})

    # 2. Load existing records for dedup
    existing_hashes, existing_ids = load_existing_ids()

    # 3. Deduplicate
    dedup_result = deduplicate_batch(all_raw, existing_hashes, existing_ids)
    new_jobs = dedup_result.new_jobs
    logger.info(f"After dedup: {len(new_jobs)} new jobs ({len(dedup_result.duplicate_ids)} duplicates)")

    # 4. Upsert to PostgreSQL
    counts = upsert_jobs(new_jobs)

    # 5. Mark expired jobs
    active_by_source: dict[str, list[str]] = {}
    for job in all_raw:
        active_by_source.setdefault(job.source, []).append(job.external_id)
    expired_count = mark_expired_jobs(active_by_source)

    # 6. Queue embedding tasks for new jobs
    # (We need job UUIDs — query back the ones we just inserted)
    from sqlalchemy import text
    from app.database import get_sync_engine
    engine = get_sync_engine()
    with engine.connect() as conn:
        new_job_ids = [
            row[0] for row in conn.execute(text(
                "SELECT id FROM jobs WHERE embedding_id IS NULL AND is_active = TRUE LIMIT 5000"
            ))
        ]
        # Jobs with no job_skills rows yet (LLM skill extraction not run) — usually the
        # same set as new_job_ids, but a broader LEFT JOIN also sweeps up any job that
        # was inserted but never got skill-extracted (e.g. worker was down).
        unskilled_job_ids = [
            row[0] for row in conn.execute(text("""
                SELECT j.id FROM jobs j
                LEFT JOIN job_skills js ON js.job_id = j.id
                WHERE j.is_active = TRUE
                GROUP BY j.id
                HAVING COUNT(js.skill_id) = 0
                LIMIT 5000
            """))
        ]
    queued = queue_embedding_tasks(new_job_ids)
    skills_queued = queue_skill_extraction_tasks(unskilled_job_ids)

    duration_s = (datetime.now(timezone.utc) - flow_start).total_seconds()

    summary = {
        "duration_s":    round(duration_s, 1),
        "total_fetched": len(all_raw),
        "new_jobs":      counts["inserted"],
        "duplicates":    len(dedup_result.duplicate_ids),
        "expired":       expired_count,
        "embed_queued":  queued,
        "skills_queued": skills_queued,
        "errors":        counts["failed"],
    }
    logger.info("Ingestion flow complete", extra={"extra": summary})
    return summary


if __name__ == "__main__":
    asyncio.run(ingest_all_jobs())
