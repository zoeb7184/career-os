"""
data-pipeline/transformers/skill_normalizer.py
────────────────────────────────────────────────
Node: etl_skills

Normalises raw skill strings → canonical skill names.
"python3", "Python", "py", "PYTHON" → "Python"

Two-stage pipeline:
  Stage 1: Exact match against canonical names + aliases (fast, free)
  Stage 2: Fuzzy match using rapidfuzz (handles typos, slight variations)

Error codes:
    SKL_001 — Taxonomy is empty (first run / DB not seeded)
    SKL_002 — Fuzzy library not available
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError

logger = get_logger("etl_skills")


class SkillError(NodeError):
    pass


# ── Built-in taxonomy (seed data) ─────────────────────────────────
# Format: canonical_name → [aliases]
# This is loaded into the skills DB table on first run.
SKILL_TAXONOMY: dict[str, list[str]] = {
    # Languages
    "Python":       ["python3", "python 3", "py", "python2", "cpython"],
    "R":            ["r-lang", "r language", "rlang"],
    "SQL":          ["sql query", "structured query language"],
    "Java":         ["java8", "java 8", "java11", "java 11", "jvm"],
    "Scala":        ["scala lang"],
    "Julia":        [],
    "Go":           ["golang", "go lang"],
    "Rust":         [],
    "C++":          ["cpp", "c plus plus", "cplusplus"],
    "JavaScript":   ["js", "javascript es6", "ecmascript", "node.js", "nodejs"],
    "TypeScript":   ["ts", "typescript"],

    # ML / Data Science
    "Machine Learning": ["ml", "machine-learning", "statistical learning"],
    "Deep Learning":    ["dl", "deep-learning", "neural networks", "ann"],
    "NLP":              ["natural language processing", "text mining", "computational linguistics"],
    "Computer Vision":  ["cv", "image recognition", "object detection"],
    "Reinforcement Learning": ["rl", "reinforcement-learning"],
    "MLOps":            ["ml ops", "ml operations", "model ops", "modelops"],

    # Frameworks
    "PyTorch":          ["torch", "pytorch"],
    "TensorFlow":       ["tensorflow 2", "tf", "tf2"],
    "Keras":            [],
    "scikit-learn":     ["sklearn", "scikit learn", "sci-kit learn"],
    "Hugging Face":     ["huggingface", "transformers library", "hf"],
    "LangChain":        ["langchain"],
    "LlamaIndex":       ["llama index", "llamaindex"],
    "XGBoost":          ["xgb", "xgboost"],
    "LightGBM":         ["lgbm", "lightgbm"],
    "CatBoost":         [],
    "Spark":            ["apache spark", "pyspark", "spark ml"],
    "FastAPI":          ["fast api"],
    "Django":           [],
    "Flask":            [],
    "React":            ["reactjs", "react.js"],
    "Next.js":          ["nextjs", "next js"],

    # Data tools
    "Pandas":           ["pandas dataframe", "pd"],
    "NumPy":            ["numpy", "np"],
    "Matplotlib":       [],
    "Seaborn":          [],
    "Plotly":           [],
    "dbt":              ["data build tool"],
    "Airflow":          ["apache airflow"],
    "Prefect":          [],
    "Dagster":          [],
    "Kafka":            ["apache kafka"],
    "Spark":            ["pyspark", "apache spark"],

    # Databases
    "PostgreSQL":       ["postgres", "postgresql", "psql"],
    "MySQL":            [],
    "MongoDB":          ["mongo"],
    "Redis":            [],
    "Elasticsearch":    ["elastic search", "elastic"],
    "Snowflake":        [],
    "BigQuery":         ["google bigquery", "bq"],
    "Redshift":         ["amazon redshift", "aws redshift"],
    "Databricks":       [],

    # Cloud
    "AWS":              ["amazon web services", "amazon aws"],
    "GCP":              ["google cloud", "google cloud platform"],
    "Azure":            ["microsoft azure", "ms azure"],

    # MLOps / DevOps
    "Docker":           ["containers", "containerisation", "containerization"],
    "Kubernetes":       ["k8s", "kubernetes cluster"],
    "MLflow":           ["ml flow"],
    "Weights & Biases": ["wandb", "weights and biases"],
    "Git":              ["github", "gitlab", "version control"],
    "CI/CD":            ["continuous integration", "continuous deployment", "devops"],

    # LLMs / AI
    "LLMs":             ["large language models", "gpt", "llm", "generative ai", "gen ai"],
    "RAG":              ["retrieval augmented generation", "retrieval-augmented generation"],
    "OpenAI":           ["openai api", "chatgpt api", "gpt-4", "gpt4", "gpt-3.5"],
    "Prompt Engineering": ["prompting", "prompt design"],

    # Stats / Math
    "Statistics":       ["statistical analysis", "stats", "statistical modelling"],
    "Mathematics":      ["linear algebra", "calculus", "probability theory"],
    "A/B Testing":      ["ab testing", "experiment design", "hypothesis testing"],
    "Time Series":      ["time-series", "timeseries", "forecasting"],

    # Soft skills
    "Communication":    ["written communication", "verbal communication", "presentation skills"],
    "Problem Solving":  ["analytical thinking", "critical thinking"],
    "Teamwork":         ["collaboration", "cross-functional"],
}

# Build reverse lookup: lowercase alias → canonical name
_ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in SKILL_TAXONOMY.items():
    _ALIAS_MAP[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_MAP[alias.lower()] = canonical


def normalise_skill(raw: str) -> str | None:
    """
    Normalise a single raw skill string → canonical name.

    Returns canonical name if found, None if completely unknown.

    Stage 1: Exact match (lowercase)
    Stage 2: Fuzzy match via rapidfuzz
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip().lower()
    cleaned = re.sub(r"[^\w\s\+\#\.]", "", cleaned)   # remove special chars except +, #, .

    # Stage 1 — exact match
    if cleaned in _ALIAS_MAP:
        return _ALIAS_MAP[cleaned]

    # Stage 2 — fuzzy match
    try:
        from rapidfuzz import process, fuzz
        match = process.extractOne(
            cleaned,
            _ALIAS_MAP.keys(),
            scorer=fuzz.ratio,
            score_cutoff=85,    # 85% similarity threshold
        )
        if match:
            matched_alias = match[0]
            canonical = _ALIAS_MAP[matched_alias]
            logger.info(
                "Fuzzy skill match",
                extra={"extra": {"raw": raw, "matched_alias": matched_alias,
                                 "canonical": canonical, "score": match[1]}}
            )
            return canonical
    except ImportError:
        raise SkillError("SKL_002", "rapidfuzz not installed", status_code=500)

    # Unknown skill
    return None


def normalise_skills(raw_skills: list[str]) -> dict[str, str | None]:
    """
    Normalise a list of raw skill strings.

    Returns:
        Dict mapping raw_skill → canonical_name (or None if unknown)

    Example:
        {"python3": "Python", "TENSORFLOW": "TensorFlow", "juggling": None}
    """
    return {raw: normalise_skill(raw) for raw in raw_skills}


def get_taxonomy() -> dict[str, list[str]]:
    """Return the full taxonomy dict. Used to seed the skills table."""
    return SKILL_TAXONOMY
