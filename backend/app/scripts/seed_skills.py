"""
backend/app/scripts/seed_skills.py
────────────────────────────────────
Seeds the skills table with the canonical skill taxonomy.
Run ONCE after alembic upgrade head:
  docker exec career-os-api python -m app.scripts.seed_skills

Idempotent — safe to run multiple times (uses INSERT ... ON CONFLICT DO NOTHING).
"""
import uuid
import sys
import os
sys.path.insert(0, '/app')

from sqlalchemy import text
from app.database import get_sync_engine
from app.logger import get_logger

# Import taxonomy from the normalizer
sys.path.insert(0, '/pkgs')
from data_pipeline.transformers.skill_normalizer import SKILL_TAXONOMY

logger = get_logger("seed_skills")

# Skill categories
CATEGORY_MAP = {
    "Python": "language", "R": "language", "SQL": "language", "Java": "language",
    "Scala": "language", "Julia": "language", "Go": "language", "Rust": "language",
    "C++": "language", "JavaScript": "language", "TypeScript": "language",
    "Machine Learning": "ml", "Deep Learning": "ml", "NLP": "ml",
    "Computer Vision": "ml", "Reinforcement Learning": "ml", "MLOps": "ml",
    "PyTorch": "framework", "TensorFlow": "framework", "Keras": "framework",
    "scikit-learn": "framework", "Hugging Face": "framework", "LangChain": "framework",
    "LlamaIndex": "framework", "XGBoost": "framework", "LightGBM": "framework",
    "CatBoost": "framework", "Spark": "framework", "FastAPI": "framework",
    "Django": "framework", "Flask": "framework", "React": "framework", "Next.js": "framework",
    "Pandas": "library", "NumPy": "library", "Matplotlib": "library",
    "Seaborn": "library", "Plotly": "library", "dbt": "tool",
    "Airflow": "tool", "Prefect": "tool", "Dagster": "tool",
    "Kafka": "tool", "PostgreSQL": "database", "MySQL": "database",
    "MongoDB": "database", "Redis": "database", "Elasticsearch": "database",
    "Snowflake": "database", "BigQuery": "database", "Redshift": "database",
    "Databricks": "database", "AWS": "cloud", "GCP": "cloud", "Azure": "cloud",
    "Docker": "devops", "Kubernetes": "devops", "MLflow": "devops",
    "Weights & Biases": "devops", "Git": "devops", "CI/CD": "devops",
    "LLMs": "ai", "RAG": "ai", "OpenAI": "ai", "Prompt Engineering": "ai",
    "Statistics": "math", "Mathematics": "math", "A/B Testing": "math",
    "Time Series": "ml", "Communication": "soft", "Problem Solving": "soft",
    "Teamwork": "soft",
}


def seed():
    engine = get_sync_engine()
    inserted = 0
    skipped = 0

    with engine.connect() as conn:
        for canonical_name, aliases in SKILL_TAXONOMY.items():
            skill_id = str(uuid.uuid4())
            category = CATEGORY_MAP.get(canonical_name, "other")
            try:
                result = conn.execute(text("""
                    INSERT INTO skills (id, canonical_name, category, aliases)
                    VALUES (:id, :name, :category, :aliases)
                    ON CONFLICT (canonical_name) DO NOTHING
                """), {
                    "id": skill_id,
                    "name": canonical_name,
                    "category": category,
                    "aliases": aliases,
                })
                if result.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error(f"Failed to insert skill {canonical_name}: {exc}")

        conn.commit()

    logger.info(f"Skill seeding complete", extra={"extra": {
        "inserted": inserted, "skipped": skipped, "total": inserted + skipped
    }})
    print(f"✅ Skills seeded: {inserted} inserted, {skipped} already existed")


if __name__ == "__main__":
    seed()
