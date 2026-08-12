"""
data-pipeline/connectors/remotive.py
──────────────────────────────────────
Node: data_remotive

Fetches remote tech jobs from Remotive.com.
No API key required — completely free and open.
https://remotive.com/api

Best for: remote ML/Data Science/Engineering roles worldwide.

Error codes:
    REM_001 — API unreachable / timeout
    REM_002 — Schema parse error
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from data_pipeline.connectors.base import BaseConnector, RawJob

logger = get_logger("data_remotive")

BASE_URL   = "https://remotive.com/api/remote-jobs"
CATEGORIES = ["software-dev", "data", "devops-sysadmin"]


class RemotiveError(NodeError):
    pass


class RemotiveConnector(BaseConnector):
    source_name = "remotive"

    def health_check(self) -> dict:
        try:
            resp = httpx.get(f"{BASE_URL}?limit=1", timeout=5)
            if resp.status_code == 200:
                return {"status": "ok", "detail": "Remotive API reachable (no auth needed)"}
            return {"status": "degraded", "detail": f"Status {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "detail": f"REM_001: {exc}"}

    async def fetch(self, country: str = "global", max_pages: int = 1) -> list[RawJob]:
        """Remotive returns all jobs in one response (no pagination needed)."""
        self._log_fetch_start(country)
        all_jobs: list[RawJob] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for category in CATEGORIES:
                try:
                    resp = await client.get(BASE_URL, params={"category": category, "limit": 500})
                    if resp.status_code != 200:
                        raise RemotiveError("REM_001", f"Status {resp.status_code}", status_code=503)
                    items = resp.json().get("jobs", [])
                    for item in items:
                        try:
                            all_jobs.append(self._parse_item(item))
                        except Exception as exc:
                            logger.warning("REM_002: parse error", extra={"extra": {"error": str(exc)}})
                    logger.info(f"Fetched {len(items)} Remotive jobs for category: {category}")
                except RemotiveError:
                    raise
                except Exception as exc:
                    raise RemotiveError("REM_001", f"Request failed: {exc}", status_code=503)

        logger.info(f"Total Remotive jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _parse_item(self, item: dict[str, Any]) -> RawJob:
        posted_at = None
        if item.get("publication_date"):
            try:
                posted_at = datetime.fromisoformat(item["publication_date"].replace("Z", "+00:00"))
            except ValueError:
                pass

        return RawJob(
            source      = "remotive",
            external_id = str(item["id"]),
            title       = item.get("title", "").strip(),
            company     = item.get("company_name"),
            location    = item.get("candidate_required_location", "Worldwide"),
            country     = "GLOBAL",
            remote_type = "remote",     # Remotive is all-remote by definition
            salary_min  = None,         # Remotive rarely includes salary
            salary_max  = None,
            description = item.get("description", ""),
            url         = item.get("url"),
            posted_at   = posted_at,
            raw         = item,
        )
