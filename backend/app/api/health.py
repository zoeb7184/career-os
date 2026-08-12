"""
backend/app/api/health.py
──────────────────────────
Master health endpoint — aggregates ALL node health checks.
GET /health → see every node's status in one request.
"""
import time
from fastapi import APIRouter
from app.config import settings
from app.logger import get_logger

logger = get_logger("health")
router = APIRouter()


def _check_postgres() -> dict:
    try:
        from sqlalchemy import text
        from app.database import get_sync_engine
        with get_sync_engine().connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
        return {"status": "ok", "detail": f"connected — {result:,} jobs in db"}
    except Exception as exc:
        return {"status": "error", "detail": f"POSTGRES: {exc}"}


def _check_redis() -> dict:
    try:
        import redis as r
        client = r.from_url(settings.redis_url, socket_connect_timeout=3)
        start = time.perf_counter()
        client.ping()
        ms = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "ok", "detail": f"ping {ms}ms"}
    except Exception as exc:
        return {"status": "error", "detail": f"REDIS: {exc}"}


def _check_qdrant() -> dict:
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=5)
        cols = client.get_collections().collections
        parts = []
        for c in cols:
            info = client.get_collection(c.name)
            parts.append(f"{c.name}({info.points_count:,})")
        return {"status": "ok", "detail": ", ".join(parts) or "no collections yet"}
    except Exception as exc:
        return {"status": "error", "detail": f"QDRANT: {exc}"}


def _check_data_adzuna() -> dict:
    try:
        from data_pipeline.connectors.adzuna import AdzunaConnector
        return AdzunaConnector().health_check()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_data_reed() -> dict:
    try:
        from data_pipeline.connectors.reed import ReedConnector
        return ReedConnector().health_check()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_data_remotive() -> dict:
    try:
        from data_pipeline.connectors.remotive import RemotiveConnector
        return RemotiveConnector().health_check()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_etl_dedup() -> dict:
    try:
        from data_pipeline.transformers.dedup import compute_hash
        h = compute_hash("test skill normalizer")
        assert len(h) == 64
        return {"status": "ok", "detail": "dedup hash function working"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_etl_skills() -> dict:
    try:
        from data_pipeline.transformers.skill_normalizer import normalise_skill
        assert normalise_skill("python3") == "Python"
        assert normalise_skill("TENSORFLOW") == "TensorFlow"
        return {"status": "ok", "detail": "skill normalizer working"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_skill_extractor() -> dict:
    try:
        from app.config import settings
        if not settings.groq_api_key:
            return {"status": "degraded", "detail": "GROQ_API_KEY not set"}
        from ml.skill_extractor.extractor import SkillExtractor  # noqa
        return {"status": "ok", "detail": "LLM client ready"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_ats_analyzer() -> dict:
    try:
        from ml.ats_analyzer.health import check
        return check()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_recommender() -> dict:
    try:
        from ml.recommender.recommender import JobRecommender  # noqa
        return {"status": "ok", "detail": "Recommender module importable"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_rag_advisor() -> dict:
    try:
        from app.config import settings
        if not settings.groq_api_key:
            return {"status": "degraded", "detail": "GROQ_API_KEY not set"}
        from ml.rag_advisor.advisor import RAGAdvisor  # noqa
        return {"status": "ok", "detail": "RAG advisor module importable"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_forecaster() -> dict:
    try:
        from ml.forecaster.forecaster import SkillDemandForecaster  # noqa
        return {"status": "ok", "detail": "Forecaster module importable"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health", tags=["Health"])
async def master_health() -> dict:
    """Check all nodes. Overall = ok only when all active nodes are ok."""
    nodes = {
        "postgres":        _check_postgres(),
        "redis":           _check_redis(),
        "qdrant":          _check_qdrant(),
        "data_adzuna":     _check_data_adzuna(),
        "data_reed":       _check_data_reed(),
        "data_remotive":   _check_data_remotive(),
        "etl_dedup":       _check_etl_dedup(),
        "etl_skills":      _check_etl_skills(),
        "skill_extractor": _check_skill_extractor(),
        "ats_analyzer":    _check_ats_analyzer(),
        "recommender":     _check_recommender(),
        "rag_advisor":     _check_rag_advisor(),
        "forecaster":      _check_forecaster(),
    }
    active = [v["status"] for v in nodes.values() if v["status"] != "not_started"]
    if all(s == "ok" for s in active):
        overall = "ok"
    elif any(s == "error" for s in active):
        overall = "error"
    else:
        overall = "degraded"

    return {"overall": overall, "environment": settings.environment, "nodes": nodes}
