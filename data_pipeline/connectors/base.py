"""
data-pipeline/connectors/base.py
──────────────────────────────────
Base class every job source connector must inherit.
Enforces a consistent interface: fetch() → list[RawJob]

Every connector node:
  - Has its own error codes (ADZ_xxx, REED_xxx, etc.)
  - Logs every fetch with structured JSON
  - Returns the same RawJob schema regardless of source
  - Handles retries internally via tenacity
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger

logger = get_logger("connector_base")


@dataclass
class RawJob:
    """
    Normalised job record returned by every connector.
    All sources must map their API response to this schema.
    """
    source:       str                    # "adzuna" | "reed" | "remotive"
    external_id:  str                    # source's own ID
    title:        str
    company:      str | None = None
    location:     str | None = None
    country:      str | None = None      # ISO 2-letter: "DE", "GB", "US"
    remote_type:  str | None = None      # "remote" | "hybrid" | "onsite"
    salary_min:   float | None = None    # annual EUR (normalised)
    salary_max:   float | None = None
    description:  str | None = None
    url:          str | None = None
    posted_at:    datetime | None = None
    raw:          dict[str, Any] = field(default_factory=dict)  # original API response


@dataclass
class FetchResult:
    """Summary returned by every connector after a fetch run."""
    source:          str
    total_fetched:   int = 0
    total_upserted:  int = 0
    total_skipped:   int = 0      # duplicates
    total_expired:   int = 0      # marked inactive
    errors:          list[str] = field(default_factory=list)
    duration_s:      float = 0.0


class BaseConnector(ABC):
    """
    Abstract base class for all job data connectors.

    Subclass this for every source:
        class AdzunaConnector(BaseConnector):
            source_name = "adzuna"
            ...
    """
    source_name: str = "unknown"

    @abstractmethod
    async def fetch(self, country: str = "de", max_pages: int = 10) -> list[RawJob]:
        """
        Fetch jobs from the source API.
        Must handle pagination internally.
        Must handle rate limits with exponential backoff.

        Args:
            country:   ISO 2-letter country code.
            max_pages: Safety limit on pagination.

        Returns:
            List of RawJob objects.

        Raises:
            NodeError subclass with source-specific error code.
        """
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """
        Check if this connector can reach its API.
        Returns: {"status": "ok"|"error"|"degraded", "detail": str}
        """
        ...

    def _log_fetch_start(self, country: str) -> None:
        logger.info(
            f"Fetching jobs from {self.source_name}",
            extra={"extra": {"source": self.source_name, "country": country}}
        )

    def _log_fetch_done(self, result: FetchResult) -> None:
        logger.info(
            f"Fetch complete: {self.source_name}",
            extra={"extra": {
                "source":         result.source,
                "fetched":        result.total_fetched,
                "upserted":       result.total_upserted,
                "skipped":        result.total_skipped,
                "expired":        result.total_expired,
                "duration_s":     result.duration_s,
                "error_count":    len(result.errors),
            }}
        )
