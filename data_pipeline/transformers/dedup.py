"""
data-pipeline/transformers/dedup.py
─────────────────────────────────────
Node: etl_dedup

Deduplication logic for the job ingestion pipeline.
Two jobs are considered duplicates if they share the same:
  1. (source, external_id)  — exact same job from same source
  2. description_hash        — same description from different sources

Error codes:
    DEDUP_001 — Database query failed
    DEDUP_002 — Hash computation failed (corrupted description)
"""
from __future__ import annotations
import hashlib
import uuid
from dataclasses import dataclass
from typing import Sequence

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from data_pipeline.connectors.base import RawJob

logger = get_logger("etl_dedup")


class DedupError(NodeError):
    pass


@dataclass
class DedupResult:
    total_input:    int
    new_jobs:       list[RawJob]
    duplicate_ids:  list[str]    # external_ids that were duplicates


def compute_hash(text: str | None) -> str | None:
    """SHA-256 hash of description text for cross-source dedup."""
    if not text or not text.strip():
        return None
    try:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()
    except Exception as exc:
        raise DedupError("DEDUP_002", f"Hash failed: {exc}", status_code=500)


def deduplicate_batch(jobs: list[RawJob], existing_hashes: set[str], existing_ids: set[tuple[str, str]]) -> DedupResult:
    """
    Deduplicate a batch of RawJobs against each other and against known DB records.

    Args:
        jobs:            Freshly fetched RawJob list.
        existing_hashes: Set of description_hash values already in the DB.
        existing_ids:    Set of (source, external_id) tuples already in the DB.

    Returns:
        DedupResult with new (non-duplicate) jobs and IDs of skipped duplicates.
    """
    seen_hashes: set[str]          = set(existing_hashes)
    seen_ids:    set[tuple[str,str]] = set(existing_ids)
    new_jobs:    list[RawJob]      = []
    dup_ids:     list[str]         = []

    for job in jobs:
        key = (job.source, job.external_id)

        # Check (source, external_id) — fastest check
        if key in seen_ids:
            dup_ids.append(job.external_id)
            continue

        # Check description hash — catches cross-source duplicates
        desc_hash = compute_hash(job.description)
        if desc_hash and desc_hash in seen_hashes:
            dup_ids.append(job.external_id)
            logger.info(
                "Cross-source duplicate detected",
                extra={"extra": {"source": job.source, "external_id": job.external_id}}
            )
            continue

        # Not a duplicate — accept it
        seen_ids.add(key)
        if desc_hash:
            seen_hashes.add(desc_hash)
        new_jobs.append(job)

    result = DedupResult(
        total_input=len(jobs),
        new_jobs=new_jobs,
        duplicate_ids=dup_ids,
    )
    logger.info(
        "Deduplication complete",
        extra={"extra": {
            "total_input":    result.total_input,
            "new_jobs":       len(result.new_jobs),
            "duplicates":     len(result.duplicate_ids),
        }}
    )
    return result
