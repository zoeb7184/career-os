# Career OS — Agent Handoff Document
## For: Claude Code (terminal) / Claude Cowork
## Read this entire file before touching any code.

---

## WHO IS THIS FOR?

**Student:** Zoeb Ali Khan — M.Sc. Data Science, Universität Bielefeld, graduating March 2027.
**Goal:** Build a production-grade AI Career Operating System as a flagship portfolio project.
**Stack:** FastAPI · PostgreSQL · Redis · Qdrant · Prefect · MLflow · Docker · Groq LLM · Next.js

---

## PROJECT OVERVIEW

An AI-powered career platform that:
- Ingests real job listings daily from Adzuna, Reed, Remotive APIs
- Extracts structured skills from job descriptions using Groq LLM (Llama 3)
- Analyzes resumes with an ATS scorer (embedding similarity + skill matching)
- Recommends jobs using Qdrant vector search
- Answers career questions via RAG (retrieval-augmented generation)
- Forecasts skill demand trends using Prophet
- Shows market intelligence dashboards (top skills, salaries, hiring trends)

---

## CRITICAL ARCHITECTURE RULE — READ FIRST

**Every module is a self-contained node.**

Each node has:
- Its own folder
- Its own `logger.py` → JSON structured logs with `"node": "node_name"` field
- Its own `errors.py` → custom error codes (e.g. `ATS_001`, `REC_002`)
- Its own `health.py` → health check function
- Its own `tests/` folder
- Its own `README.md`

**When something breaks:**
1. `curl http://localhost:8000/health` → see which node is down
2. Open that node's folder → read `errors.py` for error codes
3. `docker logs career-os-api 2>&1 | grep '"node": "node_name"'` → see exact error

**API response shape — ALWAYS:**
```json
{"data": <result>, "error": null}
{"data": null, "error": {"code": "ATS_001", "message": "...", "detail": {}}}
```

---

## WHAT IS ALREADY BUILT (77 files)

### Infrastructure (complete)
- `docker-compose.yml` — 6 containers: api, worker, postgres, redis, qdrant, mlflow
- `backend/Dockerfile` + `backend/Dockerfile.worker`
- `backend/app/main.py` — FastAPI app with all routers registered
- `backend/app/config.py` — all settings via pydantic-settings from .env
- `backend/app/logger.py` — shared JSON logger factory
- `backend/app/errors.py` — base NodeError class with error codes
- `backend/app/database.py` — SQLAlchemy async engine + session factory
- `backend/app/middleware/logging.py` — request/response JSON logging
- `backend/app/middleware/error_handler.py` — global error → JSON response
- `Makefile` — make dev, make health, make test, make logs N=api
- `.env.example` — all env vars documented

### Database (complete)
- `backend/alembic/` — migration setup
- `backend/alembic/versions/0001_initial.py` — creates all 7 tables:
  - `users`, `skills`, `jobs`, `job_skills`, `resumes`, `applications`, `market_snapshots`
- `backend/app/models/job.py`, `user.py`, `application.py`

### API Endpoints (complete — all registered in main.py)
- `GET /health` — master health check for all 13 nodes
- `GET /api/v1/jobs` — list/search/filter jobs (paginated)
- `GET /api/v1/jobs/{id}` — single job detail with skills
- `POST /api/v1/ats/analyze` — ATS resume analysis
- `GET /api/v1/recommend/{user_id}` — personalised job recommendations
- `POST /api/v1/advisor/ask` — RAG career Q&A
- `POST /api/v1/advisor/stream` — streaming SSE response
- `GET /api/v1/analytics/skills/top` — top skills by demand
- `GET /api/v1/analytics/remote` — remote vs hybrid vs onsite
- `GET /api/v1/analytics/companies/top` — top hiring companies
- `GET /api/v1/analytics/locations/top` — top hiring locations
- `GET /api/v1/analytics/salary` — salary by skill
- `GET /api/v1/analytics/summary` — dashboard header stats

### Data Pipeline (complete)
- `data-pipeline/connectors/base.py` — BaseConnector + RawJob + FetchResult
- `data-pipeline/connectors/adzuna.py` — Adzuna API (free, millions of jobs)
- `data-pipeline/connectors/reed.py` — Reed API (UK jobs)
- `data-pipeline/connectors/remotive.py` — Remotive (remote jobs, no key needed)
- `data-pipeline/transformers/dedup.py` — SHA-256 deduplication
- `data-pipeline/transformers/skill_normalizer.py` — 85 canonical skills + fuzzy matching
- `data-pipeline/flows/ingestion_flow.py` — Prefect daily ETL flow

### ML Nodes (complete)
- `ml/shared/embedder.py` — all-MiniLM-L6-v2 singleton (384-dim, runs locally)
- `ml/shared/llm_client.py` — Groq client (llama-3.1-8b-instant + llama-3.3-70b-versatile)
- `ml/skill_extractor/extractor.py` — LLM extracts skills from job descriptions
- `ml/ats_analyzer/analyzer.py` — ATS scorer (skill match 40pts + embedding 30pts + structural 20pts + keyword 10pts)
- `ml/recommender/recommender.py` — Qdrant ANN + re-ranking (vector 70% + skill 20% + recency 10%)
- `ml/rag_advisor/advisor.py` — RAG pipeline with intent detection + streaming
- `ml/forecaster/forecaster.py` — Prophet skill demand forecasting (30/60/90 day)

### Tests (complete)
- `backend/tests/test_health.py` — 6 tests for master health endpoint
- `ml/ats_analyzer/tests/test_analyzer.py` — 8 ATS tests
- `ml/forecaster/tests/test_forecaster.py` — 5 forecaster tests
- `ml/recommender/tests/test_recommender.py` — 4 recommender tests
- `data-pipeline/tests/test_skill_normalizer.py` — 9 normalizer tests

### Celery Workers (complete)
- `backend/app/workers/celery_app.py` — Celery instance, queues: ats, embeddings, default
- `backend/app/workers/ats_worker.py` — async ATS analysis task
- `backend/app/workers/embed_worker.py` — async embedding task

---

## WHAT IS MISSING (your job to build)

### MISSING 1: Auth System (HIGH PRIORITY — blocks everything else)
**File to create:** `backend/app/api/auth.py`
**What it needs:**
- `POST /api/v1/auth/register` — email + password → create user, return JWT
- `POST /api/v1/auth/login` — email + password → return JWT
- `GET /api/v1/auth/me` — return current user from JWT
- `POST /api/v1/auth/google` — Google OAuth flow
- JWT middleware: `get_current_user` dependency used by protected endpoints
- Password hashing using `passlib[bcrypt]` (already in requirements)
- JWT using `python-jose` (already in requirements)

**Wire it into main.py:**
```python
from app.api.auth import router as auth_router
app.include_router(auth_router, prefix=f"{settings.api_prefix}/auth", tags=["Auth"])
```

---

### MISSING 2: Resume Upload & Storage (HIGH PRIORITY)
**File to create:** `backend/app/api/resumes.py`
**What it needs:**
- `POST /api/v1/resumes/upload` — accept PDF/DOCX, parse text, store in DB, queue embedding
- `GET /api/v1/resumes/` — list user's resumes
- `DELETE /api/v1/resumes/{id}` — delete resume
- After upload: call `embed_resume_task.delay(resume_id)` to queue embedding

---

### MISSING 3: Application Tracker Endpoints (MEDIUM PRIORITY)
**File to create:** `backend/app/api/applications.py`
**What it needs:**
- `POST /api/v1/applications/` — save a job (status="saved")
- `GET /api/v1/applications/` — list user's applications with status
- `PATCH /api/v1/applications/{id}` — update status (applied/interview/offer/rejected)
- `DELETE /api/v1/applications/{id}` — remove

---

### MISSING 4: Embed Worker — Real Implementation (HIGH PRIORITY)
**File to update:** `backend/app/workers/embed_worker.py`
**Current state:** stub that logs and returns placeholder
**What it needs:**
```python
@celery_app.task(...)
def embed_job_task(self, job_id: str) -> dict:
    # 1. Load job description from DB
    # 2. Generate embedding via ml/shared/embedder.py
    # 3. Upsert to Qdrant 'jobs' collection
    # 4. Update jobs.embedding_id in PostgreSQL
    # Return {"status": "ok", "job_id": job_id}

def embed_resume_task(self, resume_id: str) -> dict:
    # 1. Load resume raw_text from DB
    # 2. Generate embedding (use embed_chunks for long resumes)
    # 3. Upsert to Qdrant 'resumes' collection
    # 4. Update resumes.embedding_id in PostgreSQL
```

---

### MISSING 5: Market Snapshots Daily Job (MEDIUM PRIORITY)
**File to create:** `data-pipeline/flows/snapshot_flow.py`
**What it needs:**
- Prefect flow that runs daily after ingestion
- For each skill in the skills table: count active jobs requiring it → insert into market_snapshots
- This feeds the forecaster — without it the forecaster has no data
```python
@flow(name="daily-market-snapshot")
def create_market_snapshot():
    # INSERT INTO market_snapshots (snapshot_date, skill_id, country, demand)
    # SELECT CURRENT_DATE, js.skill_id, j.country, COUNT(*)
    # FROM job_skills js JOIN jobs j ON js.job_id = j.id
    # WHERE j.is_active = TRUE
    # GROUP BY js.skill_id, j.country
```

---

### MISSING 6: Seed Skills Table (HIGH PRIORITY — first-run setup)
**File to create:** `backend/app/scripts/seed_skills.py`
**What it needs:**
- Read the SKILL_TAXONOMY from `data_pipeline/transformers/skill_normalizer.py`
- Insert all canonical skills + aliases into the `skills` table
- Must run ONCE after `alembic upgrade head`
- Add to Makefile: `make seed`

---

### MISSING 7: Frontend (Next.js) — NOT STARTED
**Directory:** `frontend/` (folder exists, completely empty)
**Pages needed:**
1. `app/page.tsx` — landing page
2. `app/(auth)/login/page.tsx` — login form
3. `app/(auth)/register/page.tsx` — register form
4. `app/dashboard/page.tsx` — user dashboard (recent apps, ATS score, top job matches)
5. `app/jobs/page.tsx` — job search with filters (keyword, country, remote, salary)
6. `app/ats/page.tsx` — upload resume + select job + show ATS score breakdown
7. `app/analytics/page.tsx` — market intelligence charts (Recharts)
8. `app/advisor/page.tsx` — RAG chatbot UI with streaming
9. `app/tracker/page.tsx` — Kanban board (saved → applied → interview → offer/rejected)

**Tech:** Next.js 14 App Router · TypeScript · Tailwind CSS · Recharts (for charts) · shadcn/ui (for components)

**API client:** `frontend/lib/api.ts` — typed fetch wrapper pointing to `http://localhost:8000`

---

### MISSING 8: GitHub Actions CI/CD
**File to create:** `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ ml/ -v --tb=short
      - run: ruff check backend/
```

---

### MISSING 9: MLflow Integration in ATS Analyzer
**File to update:** `ml/ats_analyzer/analyzer.py`
**Add to the `analyze()` method:**
```python
import mlflow
mlflow.set_experiment(settings.mlflow_experiment_ats)
with mlflow.start_run():
    mlflow.log_params({"required_skills_count": len(required_skills), "job_id": job_id})
    mlflow.log_metrics({
        "overall_score": result.overall_score,
        "skill_match": result.breakdown.skill_match,
        "embedding_sim": result.breakdown.embedding_sim,
    })
```

---

## ENVIRONMENT VARIABLES

User has a `.env` file in the project root with:
```
GROQ_API_KEY=gsk_...          # Groq free API key (set)
ADZUNA_APP_ID=...              # Adzuna job API (set)
ADZUNA_APP_KEY=...             # Adzuna job API (set)
REED_API_KEY=...               # Reed UK jobs API (set)
POSTGRES_PASSWORD=career_pass  # (set)
JWT_SECRET_KEY=mycareeros2024supersecretkey  # (set)
# Everything else is default from .env.example
```

**LLM Provider:** Groq (NOT OpenAI)
- `llm_client.py` points to `https://api.groq.com/openai/v1`
- Extraction model: `llama-3.1-8b-instant`
- Advisor model: `llama-3.3-70b-versatile`
- Uses OpenAI SDK with custom base_url — no code changes needed to use it

---

## KNOWN ISSUES TO FIX

### Issue 1: requirements.txt has `torch` dependency via sentence-transformers
**Problem:** `sentence-transformers` pulls in PyTorch which is ~2GB. This caused Docker build timeouts.
**Fix:** Split requirements into two files:
- `requirements.txt` — everything except sentence-transformers
- `requirements-ml.txt` — sentence-transformers + torch
Or use a lighter embedding alternative: `fastembed` (much smaller, same quality)

**Recommended fix — replace in requirements.txt:**
```
# Remove:
sentence-transformers==3.0.1

# Add:
fastembed==0.3.6
```
Then update `ml/shared/embedder.py` to use fastembed:
```python
from fastembed import TextEmbedding
model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
vectors = list(model.embed(texts))
```

### Issue 2: docker-compose mlflow needs a separate DB
**Problem:** MLflow tries to connect to `career_os_mlflow` database which doesn't exist.
**Fix:** Add to `backend/alembic/versions/0001_initial.py` or create a separate init script:
```sql
CREATE DATABASE career_os_mlflow;
```
Or simpler: change MLflow backend to use SQLite by updating docker-compose.yml:
```yaml
command: >
  mlflow server
  --host 0.0.0.0
  --port 5000
  --backend-store-uri sqlite:///mlflow/mlflow.db
  --default-artifact-root /mlflow/artifacts
```

### Issue 3: data-pipeline imports need sys.path fixes
**Problem:** Files in `data-pipeline/` and `ml/` use `sys.path.insert()` hacks to import from `backend/app/`.
**Better fix:** Add a `pyproject.toml` at the root level that makes all packages importable:
```toml
[tool.pytest.ini_options]
pythonpath = ["backend", ".", "ml", "data-pipeline"]
```
And set `PYTHONPATH=backend:.:ml:data-pipeline` in docker-compose environment.

---

## STARTUP SEQUENCE (what to run in order)

```bash
# 1. Start all containers
make dev

# 2. Run database migrations (first time only)
make migrate
# = docker exec career-os-api alembic upgrade head

# 3. Seed the skills table (first time only)
docker exec career-os-api python -m app.scripts.seed_skills
# (you need to create this script — see MISSING 6 above)

# 4. Run the ETL to get real jobs
docker exec career-os-api python -m data_pipeline.flows.ingestion_flow

# 5. Check everything is working
make health
# Expected: postgres=ok, redis=ok, qdrant=ok, all nodes=ok/degraded

# 6. Open API docs
open http://localhost:8000/docs
```

---

## PROJECT FILE TREE (complete)

```
career-os/
├── .env                          ← user's actual env (not in git)
├── .env.example                  ← template
├── .gitignore
├── docker-compose.yml            ← 6 services
├── Makefile                      ← make dev/test/health/logs/migrate
├── README.md
├── HANDOFF.md                    ← this file
│
├── backend/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   ├── alembic.ini
│   ├── requirements.txt          ← ⚠️ has torch via sentence-transformers (fix this)
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial.py   ← creates all 7 tables
│   ├── app/
│   │   ├── main.py               ← FastAPI app, all routers registered
│   │   ├── config.py             ← settings (Groq, not OpenAI)
│   │   ├── database.py           ← SQLAlchemy async
│   │   ├── logger.py             ← JSON logger factory
│   │   ├── errors.py             ← NodeError base class
│   │   ├── api/
│   │   │   ├── health.py         ← GET /health (13 nodes)
│   │   │   ├── jobs.py           ← GET /jobs, GET /jobs/{id}
│   │   │   ├── ats.py            ← POST /ats/analyze
│   │   │   ├── recommend.py      ← GET /recommend/{user_id}
│   │   │   ├── advisor.py        ← POST /advisor/ask + stream
│   │   │   ├── analytics.py      ← GET /analytics/*
│   │   │   ├── auth.py           ← ❌ MISSING — create this
│   │   │   ├── resumes.py        ← ❌ MISSING — create this
│   │   │   └── applications.py   ← ❌ MISSING — create this
│   │   ├── middleware/
│   │   │   ├── logging.py
│   │   │   └── error_handler.py
│   │   ├── models/
│   │   │   ├── job.py
│   │   │   ├── user.py
│   │   │   └── application.py
│   │   └── workers/
│   │       ├── celery_app.py
│   │       ├── ats_worker.py
│   │       └── embed_worker.py   ← ⚠️ stub — needs real implementation
│   └── tests/
│       └── test_health.py
│
├── data-pipeline/
│   ├── connectors/
│   │   ├── base.py               ← BaseConnector + RawJob
│   │   ├── adzuna.py             ← Adzuna API (error codes: ADZ_xxx)
│   │   ├── reed.py               ← Reed API (error codes: REED_xxx)
│   │   └── remotive.py           ← Remotive (no key needed)
│   ├── transformers/
│   │   ├── dedup.py              ← SHA-256 deduplication
│   │   └── skill_normalizer.py   ← 85 skills + fuzzy match
│   ├── flows/
│   │   ├── ingestion_flow.py     ← Prefect daily ETL
│   │   └── snapshot_flow.py      ← ❌ MISSING — daily market_snapshots
│   └── tests/
│       └── test_skill_normalizer.py
│
├── ml/
│   ├── shared/
│   │   ├── embedder.py           ← ⚠️ uses sentence-transformers (fix to fastembed)
│   │   └── llm_client.py         ← Groq client (OpenAI SDK, custom base_url)
│   ├── skill_extractor/
│   │   └── extractor.py          ← GPT/Groq structured skill extraction
│   ├── ats_analyzer/
│   │   ├── analyzer.py           ← ATS scorer (40+30+20+10 pts)
│   │   ├── errors.py             ← ATS_001 through ATS_005
│   │   ├── health.py             ← health check
│   │   └── tests/test_analyzer.py
│   ├── recommender/
│   │   ├── recommender.py        ← Qdrant ANN + re-ranking
│   │   └── tests/test_recommender.py
│   ├── rag_advisor/
│   │   └── advisor.py            ← RAG + intent detection + streaming
│   └── forecaster/
│       ├── forecaster.py         ← Prophet 30/60/90-day forecasting
│       └── tests/test_forecaster.py
│
└── frontend/                     ← ❌ EMPTY — entire Next.js app to build
    ├── app/
    ├── components/
    ├── lib/
    └── public/
```

---

## PRIORITY ORDER FOR COMPLETION

### Priority 1 — Make it run (do these first)
1. Fix `requirements.txt`: replace `sentence-transformers` with `fastembed`
2. Fix MLflow: change to SQLite backend in docker-compose.yml
3. Fix PYTHONPATH in docker-compose.yml environment section
4. Run `make dev` → `make migrate` → confirm `/health` returns ok
5. Create `backend/app/scripts/seed_skills.py` → seed skills table
6. Implement real `embed_worker.py` (embed jobs → Qdrant)
7. Run ingestion flow → confirm jobs appear in DB

### Priority 2 — Make it useful
8. Create `backend/app/api/auth.py` (JWT auth)
9. Create `backend/app/api/resumes.py` (resume upload)
10. Create `backend/app/api/applications.py` (tracker)
11. Create `data-pipeline/flows/snapshot_flow.py`
12. Add MLflow logging to ATS analyzer

### Priority 3 — Make it visible (the portfolio piece)
13. Build the entire Next.js frontend (9 pages)
14. Add GitHub Actions CI
15. Deploy to AWS ECS (or Railway for simpler option)
16. Record demo video

---

## HOW TO RUN TESTS

```bash
# All tests
make test

# Single node tests
make test-node N=ats_analyzer
make test-node N=recommender
make test-node N=forecaster

# Skill normalizer
docker exec career-os-api pytest /data-pipeline/tests/ -v

# Health check
curl http://localhost:8000/health | python3 -m json.tool
```

---

## USEFUL COMMANDS

```bash
make dev              # start all containers
make down             # stop all containers
make health           # curl /health + pretty print
make logs N=api       # tail API logs
make logs N=worker    # tail Celery worker logs
make migrate          # run alembic upgrade head
make test             # run all tests
make lint             # ruff + mypy

# Manual ingestion run
docker exec career-os-api python -m data_pipeline.flows.ingestion_flow

# Check jobs in DB
docker exec career-os-postgres psql -U career_user -d career_os -c "SELECT COUNT(*) FROM jobs;"

# Check Qdrant collections
curl http://localhost:6333/collections

# MLflow UI
open http://localhost:5000

# API docs
open http://localhost:8000/docs
```

---

## CONTEXT FOR NEW SESSIONS

If starting a new chat session, paste this:

```
PROJECT: AI Career Operating System (career-os folder)
STACK: FastAPI + PostgreSQL + Redis + Qdrant + Groq LLM + Next.js + Docker
ARCHITECTURE: Every module is a self-contained node with its own logger, error codes, health check, and tests.
LLM: Groq (free) — llama-3.1-8b-instant for extraction, llama-3.3-70b-versatile for advisor
CURRENT STATE: Backend + ML nodes + data pipeline complete (77 files). Frontend missing. Auth missing. Embed worker is a stub.
IMMEDIATE TASK: [describe what you're working on]
HANDOFF FILE: Read HANDOFF.md in project root for full context.
```

---

*Last updated: Session where Docker disk space was freed (20GB reclaimed via docker system prune) and make dev was about to be re-run after cleanup.*
