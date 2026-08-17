"""
backend/app/config.py
─────────────────────
All configuration comes from environment variables.
Never hardcode secrets. Access settings via: from app.config import settings
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "DEBUG"
    api_prefix: str = "/api/v1"
    # Plain string on purpose: pydantic-settings JSON-decodes complex (list/dict)
    # env fields before validators ever run, which breaks on a plain comma
    # string like "http://localhost:3000". Parse it ourselves via the property below.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # ── PostgreSQL ───────────────────────────────────────────────
    postgres_url: str = "postgresql://career_user:career_pass@localhost:5432/career_os"

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Qdrant ───────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # ── Auth ─────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    # ── Google OAuth ─────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Job Data APIs ────────────────────────────────────────────
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    reed_api_key: str = ""
    the_muse_api_key: str = ""
    remotive_api_key: str = ""

    # ── AI / LLM (Groq — FREE, no credit card needed) ────────────
    # Get your free key at: https://console.groq.com
    groq_api_key: str = ""
    # llama-3.1-8b-instant / llama-3.3-70b-versatile were retired from Groq's
    # catalog — swapped for their current (2026) equivalents. Verify against
    # https://api.groq.com/openai/v1/models if this starts 404ing again.
    groq_model_extraction: str = "openai/gpt-oss-20b"         # fast for bulk skill extraction
    groq_model_advisor: str    = "openai/gpt-oss-120b"        # smarter for RAG Q&A

    # Local embedding model — runs on your machine, zero API cost
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── AWS ──────────────────────────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-central-1"
    s3_bucket: str = "career-os-resumes"

    # ── MLflow ───────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_ats: str = "ats_analyzer"
    mlflow_experiment_rec: str = "recommender"
    mlflow_experiment_forecast: str = "forecaster"

    # ── Celery ───────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — call this everywhere."""
    return Settings()


# Convenience singleton
settings = get_settings()
