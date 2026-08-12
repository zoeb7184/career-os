"""
data-pipeline/connectors/adzuna.py
────────────────────────────────────
Node: data_adzuna

Fetches job listings from the Adzuna API.
Free tier: https://developer.adzuna.com/ (register for free App ID + Key)
Coverage: Germany (de), UK (gb), US (us), and 10+ more countries.

Error codes:
    ADZ_001 — API rate limit (429) — backs off and retries
    ADZ_002 — API authentication failed (401) — check ADZUNA_APP_ID / ADZUNA_APP_KEY
    ADZ_003 — Schema validation error on a response item — skips that item, logs it
    ADZ_004 — Network error / timeout — raises after max retries
    ADZ_005 — Database upsert failed
"""
from __future__ import annotations
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from data_pipeline.connectors.base import BaseConnector, RawJob, FetchResult

logger = get_logger("data_adzuna")

BASE_URL = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 50
CATEGORIES = ["it-jobs", "engineering-jobs", "scientific-qa-jobs"]


class AdzunaError(NodeError):
    pass


class AdzunaConnector(BaseConnector):
    source_name = "adzuna"

    def __init__(self) -> None:
        from app.config import settings
        self.app_id  = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        if not self.app_id or not self.app_key:
            logger.warning("ADZUNA_APP_ID or ADZUNA_APP_KEY not set — connector will fail on fetch")

    # ── Health check ────────────────────────────────────────────────
    def health_check(self) -> dict:
        """Quick ping: fetch 1 result from the API."""
        if not self.app_id:
            return {"status": "not_started", "detail": "ADZUNA_APP_ID not configured"}
        try:
            resp = httpx.get(
                f"{BASE_URL}/de/search/1",
                params={"app_id": self.app_id, "app_key": self.app_key, "results_per_page": 1},
                timeout=5,
            )
            if resp.status_code == 200:
                count = resp.json().get("count", "?")
                return {"status": "ok", "detail": f"API reachable, ~{count:,} DE jobs available"}
            elif resp.status_code == 401:
                return {"status": "error", "detail": "ADZ_002: Invalid credentials"}
            else:
                return {"status": "degraded", "detail": f"API returned {resp.status_code}"}
        except Exception as exc:
            return {"status": "error", "detail": f"ADZ_004: {exc}"}

    # ── Main fetch ───────────────────────────────────────────────────
    async def fetch(self, country: str = "de", max_pages: int = 10) -> list[RawJob]:
        """Fetch jobs for a country across all configured categories."""
        self._log_fetch_start(country)
        all_jobs: list[RawJob] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for category in CATEGORIES:
                for page in range(1, max_pages + 1):
                    try:
                        jobs = await self._fetch_page(client, country, category, page)
                        if not jobs:
                            break   # no more pages
                        all_jobs.extend(jobs)
                        logger.info(
                            f"Fetched page {page} of {category}",
                            extra={"extra": {"source": "adzuna", "country": country,
                                             "category": category, "page": page, "count": len(jobs)}}
                        )
                        # Polite delay between pages
                        time.sleep(0.3)
                    except AdzunaError as exc:
                        if exc.code == "ADZ_002":
                            raise   # auth errors should halt everything
                        logger.warning(
                            f"Skipping page {page} of {category}: {exc.code}",
                            extra={"extra": {"error_code": exc.code, "detail": exc.detail}}
                        )
                        break

        logger.info(f"Total jobs fetched from Adzuna ({country}): {len(all_jobs)}")
        return all_jobs

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(AdzunaError),
        reraise=True,
    )
    async def _fetch_page(
        self, client: httpx.AsyncClient, country: str, category: str, page: int
    ) -> list[RawJob]:
        """Fetch one page of results. Retries up to 3x on rate limit."""
        params = {
            "app_id":           self.app_id,
            "app_key":          self.app_key,
            "results_per_page": RESULTS_PER_PAGE,
            "what":             "data science machine learning python",
            "sort_by":          "date",
        }
        try:
            resp = await client.get(f"{BASE_URL}/{country}/search/{page}", params=params)
        except httpx.TimeoutException as exc:
            raise AdzunaError("ADZ_004", f"Request timeout: {exc}", status_code=503)
        except httpx.RequestError as exc:
            raise AdzunaError("ADZ_004", f"Network error: {exc}", status_code=503)

        if resp.status_code == 429:
            raise AdzunaError("ADZ_001", "Rate limit exceeded — will retry", {"retry": True}, status_code=429)
        if resp.status_code == 401:
            raise AdzunaError("ADZ_002", "Authentication failed — check ADZUNA_APP_ID / ADZUNA_APP_KEY", status_code=401)
        if resp.status_code != 200:
            raise AdzunaError("ADZ_004", f"Unexpected status {resp.status_code}", status_code=503)

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return []

        jobs = []
        for item in results:
            try:
                jobs.append(self._parse_item(item, country))
            except Exception as exc:
                logger.warning(
                    f"ADZ_003: Failed to parse job item",
                    extra={"extra": {"error_code": "ADZ_003", "item_id": item.get("id"), "error": str(exc)}}
                )
        return jobs

    def _parse_item(self, item: dict[str, Any], country: str) -> RawJob:
        """Map one Adzuna API result to a RawJob."""
        # Adzuna salary is annual GBP/local currency — we store as-is, normalise later
        sal_min = item.get("salary_min")
        sal_max = item.get("salary_max")

        # Parse posted date
        created = item.get("created")
        posted_at = None
        if created:
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                pass

        location = item.get("location", {})
        loc_str = ", ".join(location.get("display_name", "").split(",")[:2]) if location else None

        return RawJob(
            source      = "adzuna",
            external_id = str(item["id"]),
            title       = item.get("title", "").strip(),
            company     = item.get("company", {}).get("display_name"),
            location    = loc_str,
            country     = country.upper(),
            remote_type = self._infer_remote(item),
            salary_min  = float(sal_min) if sal_min else None,
            salary_max  = float(sal_max) if sal_max else None,
            description = item.get("description", ""),
            url         = item.get("redirect_url"),
            posted_at   = posted_at,
            raw         = item,
        )

    @staticmethod
    def _infer_remote(item: dict) -> str:
        """Infer remote type from job title + description keywords."""
        text = f"{item.get('title','')} {item.get('description','')}".lower()
        if "fully remote" in text or "100% remote" in text or "remote only" in text:
            return "remote"
        if "hybrid" in text:
            return "hybrid"
        return "onsite"
