"""
data-pipeline/connectors/reed.py
──────────────────────────────────
Node: data_reed

Fetches job listings from Reed.co.uk API.
Free tier: https://www.reed.co.uk/developers/jobseeker
Coverage: UK jobs (excellent for ML/Data Science roles in London)

Error codes:
    REED_001 — Rate limit (429)
    REED_002 — Auth failed (401) — check REED_API_KEY
    REED_003 — Schema parse error on item
    REED_004 — Network timeout
"""
from __future__ import annotations
import time
import base64
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from data_pipeline.connectors.base import BaseConnector, RawJob, FetchResult

logger = get_logger("data_reed")

BASE_URL       = "https://www.reed.co.uk/api/1.0"
RESULTS_PER_PAGE = 100
KEYWORDS       = ["data scientist", "machine learning", "data engineer", "ML engineer", "AI engineer"]


class ReedError(NodeError):
    pass


class ReedConnector(BaseConnector):
    source_name = "reed"

    def __init__(self) -> None:
        from app.config import settings
        self.api_key = settings.reed_api_key
        # Reed uses HTTP Basic Auth: api_key as username, empty password
        if self.api_key:
            credentials = base64.b64encode(f"{self.api_key}:".encode()).decode()
            self._auth_header = {"Authorization": f"Basic {credentials}"}
        else:
            self._auth_header = {}
            logger.warning("REED_API_KEY not set — connector will fail on fetch")

    def health_check(self) -> dict:
        if not self.api_key:
            return {"status": "not_started", "detail": "REED_API_KEY not configured"}
        try:
            resp = httpx.get(
                f"{BASE_URL}/search",
                headers=self._auth_header,
                params={"keywords": "data scientist", "resultsToTake": 1},
                timeout=5,
            )
            if resp.status_code == 200:
                count = resp.json().get("totalResults", "?")
                return {"status": "ok", "detail": f"API reachable, {count:,} matching jobs"}
            elif resp.status_code == 401:
                return {"status": "error", "detail": "REED_002: Invalid API key"}
            else:
                return {"status": "degraded", "detail": f"API returned {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "detail": f"REED_004: {exc}"}

    async def fetch(self, country: str = "gb", max_pages: int = 5) -> list[RawJob]:
        self._log_fetch_start(country)
        all_jobs: list[RawJob] = []

        async with httpx.AsyncClient(timeout=30, headers=self._auth_header) as client:
            for keyword in KEYWORDS:
                skip = 0
                for page in range(max_pages):
                    try:
                        jobs = await self._fetch_page(client, keyword, skip)
                        if not jobs:
                            break
                        all_jobs.extend(jobs)
                        skip += RESULTS_PER_PAGE
                        time.sleep(0.5)   # Reed asks for polite rate limiting
                    except ReedError as exc:
                        if exc.code == "REED_002":
                            raise
                        logger.warning(f"Skipping Reed page for '{keyword}': {exc.code}")
                        break

        logger.info(f"Total jobs fetched from Reed: {len(all_jobs)}")
        return all_jobs

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20),
           retry=retry_if_exception_type(ReedError), reraise=True)
    async def _fetch_page(self, client: httpx.AsyncClient, keywords: str, skip: int) -> list[RawJob]:
        try:
            resp = await client.get(
                f"{BASE_URL}/search",
                params={"keywords": keywords, "resultsToTake": RESULTS_PER_PAGE, "resultsToSkip": skip},
            )
        except httpx.TimeoutException as exc:
            raise ReedError("REED_004", f"Timeout: {exc}", status_code=503)

        if resp.status_code == 429:
            raise ReedError("REED_001", "Rate limited", status_code=429)
        if resp.status_code == 401:
            raise ReedError("REED_002", "Auth failed — check REED_API_KEY", status_code=401)
        if resp.status_code != 200:
            raise ReedError("REED_004", f"Status {resp.status_code}", status_code=503)

        results = resp.json().get("results", [])
        jobs = []
        for item in results:
            try:
                jobs.append(self._parse_item(item))
            except Exception as exc:
                logger.warning("REED_003: parse error", extra={"extra": {"error": str(exc), "id": item.get("jobId")}})
        return jobs

    def _parse_item(self, item: dict[str, Any]) -> RawJob:
        posted_at = None
        if item.get("date"):
            try:
                posted_at = datetime.strptime(item["date"], "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        return RawJob(
            source      = "reed",
            external_id = str(item["jobId"]),
            title       = item.get("jobTitle", "").strip(),
            company     = item.get("employerName"),
            location    = item.get("locationName"),
            country     = "GB",
            remote_type = "remote" if item.get("locationName", "").lower() == "remote" else "onsite",
            salary_min  = item.get("minimumSalary"),
            salary_max  = item.get("maximumSalary"),
            description = item.get("jobDescription", ""),
            url         = item.get("jobUrl"),
            posted_at   = posted_at,
            raw         = item,
        )
