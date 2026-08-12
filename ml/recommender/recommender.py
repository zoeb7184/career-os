"""
ml/recommender/recommender.py
───────────────────────────────
Node: recommender

Recommends jobs to users based on their resume embedding.
Uses Qdrant approximate nearest neighbour (ANN) search for speed.

Algorithm:
  1. Embed user's resume text (all-MiniLM-L6-v2)
  2. Query Qdrant 'jobs' collection — top 50 candidates
  3. Apply hard filters: country, remote_type, salary_min
  4. Re-rank: 0.7 × vector_sim + 0.2 × skill_overlap + 0.1 × recency
  5. Return top N

Error codes:
  REC_001 — User has no uploaded resume
  REC_002 — Qdrant query failed
  REC_003 — Insufficient jobs in database (<100)
  REC_004 — Re-ranking error
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError
from ml.shared.embedder import get_embedder

logger = get_logger("recommender")


class RecommenderError(NodeError):
    pass


@dataclass
class JobRecommendation:
    job_id:         str
    title:          str
    company:        str | None
    location:       str | None
    remote_type:    str | None
    salary_min:     float | None
    salary_max:     float | None
    posted_at:      str | None
    url:            str | None
    vector_score:   float           # cosine similarity
    skill_score:    float           # skill overlap ratio
    recency_score:  float           # how recently posted (0-1)
    final_score:    float           # weighted combination
    matched_skills: list[str] = field(default_factory=list)


@dataclass
class RecommendationResult:
    user_id:        str
    recommendations: list[JobRecommendation]
    total_candidates: int
    applied_filters: dict


class JobRecommender:
    """
    Qdrant-based job recommendation engine.
    Embeds resume → finds nearest job vectors → re-ranks → returns top N.
    """

    def __init__(self) -> None:
        self._embedder = get_embedder()

    def recommend(
        self,
        resume_text:   str,
        user_skills:   list[str],
        user_id:       str,
        top_n:         int = 20,
        country:       str | None = None,
        remote_type:   str | None = None,
        salary_min:    float | None = None,
    ) -> RecommendationResult:
        """
        Recommend jobs for a user based on their resume.

        Args:
            resume_text:  Parsed text of the user's resume.
            user_skills:  Canonical skills from the user's profile.
            user_id:      User UUID (for logging).
            top_n:        How many recommendations to return.
            country:      Filter by country code (e.g. "DE").
            remote_type:  Filter: "remote" | "hybrid" | "onsite" | None.
            salary_min:   Filter: minimum salary.

        Returns:
            RecommendationResult with ranked job list.
        """
        logger.info("Generating recommendations", extra={"extra": {
            "user_id": user_id, "top_n": top_n,
            "filters": {"country": country, "remote_type": remote_type, "salary_min": salary_min}
        }})

        # 1. Embed resume
        try:
            resume_vector = self._embedder.embed_chunks(resume_text)[0]
        except Exception as exc:
            raise RecommenderError("REC_002", f"Resume embedding failed: {exc}", status_code=503)

        # 2. Query Qdrant
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
            from app.config import settings

            client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)

            # Build payload filters
            must_conditions = []
            if country:
                must_conditions.append(FieldCondition(key="country", match=MatchValue(value=country)))
            if remote_type:
                must_conditions.append(FieldCondition(key="remote_type", match=MatchValue(value=remote_type)))
            if salary_min:
                must_conditions.append(FieldCondition(key="salary_min", range=Range(gte=salary_min)))

            qdrant_filter = Filter(must=must_conditions) if must_conditions else None

            # Fetch 50 candidates (we'll re-rank and return top_n)
            hits = client.search(
                collection_name = "jobs",
                query_vector    = resume_vector,
                query_filter    = qdrant_filter,
                limit           = 50,
                with_payload    = True,
            )
        except Exception as exc:
            raise RecommenderError("REC_002", f"Qdrant search failed: {exc}", status_code=503)

        if len(hits) < 10:
            raise RecommenderError(
                "REC_003",
                f"Not enough jobs in database to recommend ({len(hits)} found). Run ingestion pipeline first.",
                {"hit_count": len(hits)},
                status_code=503,
            )

        # 3. Re-rank candidates
        user_skills_lower = {s.lower() for s in user_skills}
        recommendations   = []
        now               = datetime.now(timezone.utc)

        for hit in hits:
            payload = hit.payload or {}
            vector_score = hit.score  # cosine similarity from Qdrant

            # Skill overlap score (0-1)
            job_skills_lower = {s.lower() for s in payload.get("skills", [])}
            if user_skills_lower and job_skills_lower:
                overlap = len(user_skills_lower.intersection(job_skills_lower))
                skill_score = overlap / max(len(user_skills_lower), len(job_skills_lower))
            else:
                skill_score = 0.0

            # Recency score (0-1): exponential decay, half-life 14 days
            posted_str = payload.get("posted_at")
            recency_score = 0.5   # default: unknown age
            if posted_str:
                try:
                    posted_dt  = datetime.fromisoformat(posted_str)
                    days_old   = (now - posted_dt.replace(tzinfo=timezone.utc)).days
                    recency_score = math.exp(-days_old / 14)   # half-life = 14 days
                except (ValueError, TypeError):
                    pass

            final_score = (
                0.70 * vector_score  +
                0.20 * skill_score   +
                0.10 * recency_score
            )

            matched = [s for s in payload.get("skills", []) if s.lower() in user_skills_lower]

            recommendations.append(JobRecommendation(
                job_id         = payload.get("job_id", hit.id),
                title          = payload.get("title", ""),
                company        = payload.get("company"),
                location       = payload.get("location"),
                remote_type    = payload.get("remote_type"),
                salary_min     = payload.get("salary_min"),
                salary_max     = payload.get("salary_max"),
                posted_at      = payload.get("posted_at"),
                url            = payload.get("url"),
                vector_score   = round(vector_score, 4),
                skill_score    = round(skill_score, 4),
                recency_score  = round(recency_score, 4),
                final_score    = round(final_score, 4),
                matched_skills = matched,
            ))

        # Sort by final score descending
        recommendations.sort(key=lambda r: r.final_score, reverse=True)
        top = recommendations[:top_n]

        logger.info("Recommendations generated", extra={"extra": {
            "user_id":   user_id,
            "candidates": len(hits),
            "returned":   len(top),
            "top_score":  top[0].final_score if top else 0,
        }})

        return RecommendationResult(
            user_id          = user_id,
            recommendations  = top,
            total_candidates = len(hits),
            applied_filters  = {"country": country, "remote_type": remote_type, "salary_min": salary_min},
        )
