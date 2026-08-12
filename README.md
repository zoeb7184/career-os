# Career OS — AI-Powered Career Operating System

> A portfolio project demonstrating end-to-end Data Science, ML Engineering, LLMs, RAG, MLOps, and Full-Stack Development.

## Live Demo
🔗 _Coming soon — deploying to AWS ECS_

## Architecture
![Architecture Diagram](docs/architecture.png)

**Stack:** Next.js · FastAPI · PostgreSQL · Qdrant · Redis · Prefect · MLflow · Docker · AWS

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Fill in your API keys in .env

# 2. Start everything
make dev

# 3. Verify all nodes
make health
# → http://localhost:8000/health

# 4. View API docs
open http://localhost:8000/docs
```

## Node Health
Every module is a self-contained node. Check all at once:
```bash
curl http://localhost:8000/health | python3 -m json.tool
```

## Project Structure
```
career-os/
├── backend/          FastAPI + Celery
├── frontend/         Next.js + Tailwind
├── data_pipeline/    Prefect ETL flows + connectors
├── ml/               All ML nodes (ATS, recommender, RAG, forecaster)
├── docs/             Architecture + ML decisions
└── infrastructure/   Docker + Terraform
```

## ML Components
| Node | Technology | Status |
|------|-----------|--------|
| Skill extraction | GPT-4o-mini + structured output | Phase 2 |
| ATS analyzer | sentence-transformers + rule-based | Phase 2 |
| Recommender | Qdrant ANN + re-ranking | Phase 3 |
| RAG advisor | GPT-4o-mini + Qdrant retrieval | Phase 3 |
| Forecaster | Prophet | Phase 3 |

## Development Phases
- **Phase 1** (Weeks 1–4): Infrastructure, ETL pipeline, job ingestion ← *current*
- **Phase 2** (Weeks 5–8): LLM extraction, ATS analyzer, MLflow
- **Phase 3** (Weeks 9–16): Recommender, analytics, RAG advisor, forecasting
- **Phase 4** (Weeks 17–24): Polish, CI/CD, production deployment

## Debug Guide
When something breaks:
1. `make health` — identify the broken node
2. Open that node's folder → read `errors.py` for error codes
3. `make logs N=api | grep '"node": "<node_name>"'` — see exact error + line number
