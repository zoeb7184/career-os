<div align="center">

# 🎯 Career OS
### AI-Powered Career Operating System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**A production-grade platform combining job discovery, ATS resume analysis, AI career advice, and labor market intelligence — built as a full Data Science portfolio project.**

[Live Demo](#) · [API Docs](http://localhost:8000/docs) · [Report Bug](https://github.com/zoeb7184/career-os/issues)

</div>

---

## 📌 What is Career OS?

Career OS is a unified AI platform for students and job seekers that replaces scattered tools like LinkedIn Premium, Jobscan, Teal, and Huntr with a single system. It ingests real job data daily, analyzes resumes with ML, recommends jobs using vector similarity, and answers career questions via a RAG-powered advisor — all running on a production-grade microservice architecture.

> Built by **Zoeb Ali Khan** — M.Sc. Data Science, Universität Bielefeld

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| 🔍 **Job Aggregation** | Daily ingestion from Adzuna, Reed, and Remotive APIs — 679+ real jobs, deduplicated and normalized |
| 🧠 **ATS Resume Analyzer** | Upload your CV and get a score (0–100) broken down by skill match, semantic similarity, structure, and keyword density |
| 🎯 **Job Recommender** | Qdrant vector search matches your resume embedding to the most relevant jobs with re-ranking |
| 💬 **AI Career Advisor** | RAG chatbot backed by live job data — answers questions like "Which skills should I learn next?" |
| 📊 **Market Intelligence** | Real-time dashboards showing top skills, salary ranges, hiring companies, remote vs onsite trends |
| 📈 **Demand Forecasting** | Prophet time-series models forecast 30/60/90-day skill demand trends |
| 📋 **Application Tracker** | Kanban board — drag applications from Saved → Applied → Interview → Offer/Rejected |
| 🔐 **Auth System** | JWT authentication with email/password and Google OAuth |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│              Next.js 14 · TypeScript · Tailwind             │
│         Jobs · ATS · Analytics · Advisor · Tracker          │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                         │
│        9 routers · JWT auth · Celery workers                │
│     JSON logging · Error codes · Master /health endpoint    │
└───┬──────────┬────────────┬────────────┬────────────────────┘
    │          │            │            │
┌───▼──┐  ┌───▼───┐  ┌─────▼──┐  ┌─────▼──────┐
│ PG   │  │ Redis │  │ Qdrant │  │  MLflow    │
│ SQL  │  │ Cache │  │Vectors │  │ Tracking   │
└──────┘  └───────┘  └────────┘  └────────────┘
    │
┌───▼─────────────────────────────────────────────────────────┐
│                    ML / AI Layer                            │
│  Skill Extractor · ATS Analyzer · Recommender               │
│  RAG Advisor · Forecaster · Embedder (fastembed)            │
│                   LLM: Groq (Llama 3)                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  Data Pipeline (Prefect)                    │
│         Adzuna · Reed · Remotive → ETL → Normalize          │
│              Dedup · Skill Extract · Embed                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧱 Tech Stack

### Backend
- **FastAPI** — async REST API with 9 routers, JWT auth, SSE streaming
- **PostgreSQL 16** — 7 normalized tables (jobs, users, skills, resumes, applications, market_snapshots)
- **Redis** — Celery broker + response caching
- **Celery** — async workers for ATS analysis and embedding generation
- **Alembic** — database migrations

### ML / AI
- **Groq LLM** (Llama 3.1 8B + 70B) — skill extraction and RAG advisor (free tier)
- **fastembed** — local sentence embeddings (all-MiniLM-L6-v2, 384-dim, zero API cost)
- **Qdrant** — vector database for job and resume embeddings
- **Prophet** — time-series forecasting for skill demand
- **scikit-learn + rapidfuzz** — skill normalization and matching

### Data Pipeline
- **Prefect** — orchestrated ETL flows (daily ingestion + market snapshots)
- **Adzuna API** — millions of real job listings
- **Reed API** — UK tech job listings
- **Remotive API** — remote jobs (no key required)

### Frontend
- **Next.js 14** App Router + TypeScript
- **Tailwind CSS** + shadcn/ui components
- **Recharts** — market intelligence visualizations
- **SSE streaming** — real-time advisor chat responses

### Infrastructure
- **Docker Compose** — 6 services orchestrated locally
- **MLflow** — experiment tracking for ATS and recommender models
- **GitHub Actions** — CI on every push

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop running
- Node.js 18+
- API keys: [Groq](https://console.groq.com) (free) · [Adzuna](https://developer.adzuna.com) (free) · [Reed](https://www.reed.co.uk/developers) (free)

### 1. Clone and configure
```bash
git clone https://github.com/zoeb7184/career-os.git
cd career-os
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Start everything
```bash
make dev          # starts all 6 Docker containers
make setup        # runs DB migrations + seeds skill taxonomy
make ingest       # pulls real jobs from APIs (679+ jobs)
```

### 3. Open the app
```
Frontend:   http://localhost:3001
API Docs:   http://localhost:8000/docs
MLflow:     http://localhost:5001
Qdrant:     http://localhost:6333/dashboard
```

---

## 🔍 Node Architecture

Every module is a **self-contained node** with its own:
- JSON structured logger (`"node": "ats_analyzer"` in every log line)
- Error codes (`ATS_001`, `REC_002`, `FOR_003`) for instant debugging
- Health check function aggregated at `GET /health`
- Test suite in `tests/`

**When something breaks:**
```bash
# 1. See which node is down
curl http://localhost:8000/health | python3 -m json.tool

# 2. Read that node's error codes
cat ml/ats_analyzer/errors.py

# 3. Grep logs for that node
docker logs career-os-api 2>&1 | grep '"node": "ats_analyzer"'
```

---

## 📁 Project Structure

```
career-os/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/              # 9 routers (health, auth, jobs, ats, recommend, advisor, analytics, resumes, applications)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── workers/          # Celery async tasks
│   │   └── middleware/       # JSON logging + error handling
│   └── migrations/           # Alembic DB migrations
├── ml/                       # All ML nodes
│   ├── shared/               # Embedder + LLM client (used by all nodes)
│   ├── ats_analyzer/         # Resume scoring (skill + embedding + structural + keyword)
│   ├── recommender/          # Qdrant ANN job matching
│   ├── rag_advisor/          # RAG career Q&A with intent detection
│   ├── forecaster/           # Prophet skill demand forecasting
│   └── skill_extractor/      # Groq LLM structured skill extraction
├── data-pipeline/            # ETL pipeline
│   ├── connectors/           # Adzuna, Reed, Remotive
│   ├── transformers/         # Dedup + skill normalization
│   └── flows/                # Prefect orchestration flows
├── frontend/                 # Next.js 14 app (9 pages)
├── docker-compose.yml        # 6 services
└── Makefile                  # make dev/test/health/ingest/setup
```

---

## 📊 Data Science Components

This project demonstrates the complete Data Science lifecycle:

| Component | Implementation |
|-----------|----------------|
| **Data Collection** | Multi-source API ingestion with retry logic and rate limit handling |
| **ETL Pipeline** | Prefect-orchestrated daily flows with validation and deduplication |
| **NLP** | LLM-based structured skill extraction with taxonomy normalization |
| **Embeddings** | Sentence embeddings for semantic job-resume matching |
| **Recommendation** | Approximate nearest neighbour search with multi-factor re-ranking |
| **Forecasting** | Prophet time-series with confidence intervals and trend detection |
| **RAG** | Retrieval-augmented generation with intent classification |
| **MLOps** | MLflow experiment tracking, structured logging, health monitoring |
| **Deployment** | Docker Compose, CI/CD via GitHub Actions |

---

## 🛠️ Useful Commands

```bash
make dev          # start all containers
make down         # stop all containers
make health       # check all 13 node statuses
make test         # run full test suite
make logs N=api   # tail API logs
make migrate      # run DB migrations
make seed         # seed skills taxonomy
make ingest       # run ETL ingestion
make snapshot     # create daily market snapshot
```

---

## 🧪 Testing

```bash
make test                        # all tests
make test-node N=ats_analyzer    # single node
make test-node N=recommender
make test-node N=forecaster
```

Test coverage includes unit tests for all ML nodes, API endpoint tests, health check tests, and skill normalizer tests.

---

## 📈 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | All 13 node statuses |
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT token |
| GET | `/api/v1/jobs` | Search/filter jobs |
| POST | `/api/v1/ats/analyze` | ATS resume scoring |
| GET | `/api/v1/recommend/{user_id}` | Personalised job recommendations |
| POST | `/api/v1/advisor/ask` | Career Q&A |
| POST | `/api/v1/advisor/stream` | Streaming advisor (SSE) |
| GET | `/api/v1/analytics/skills/top` | Top skills by demand |
| GET | `/api/v1/analytics/salary` | Salary ranges by skill |
| POST | `/api/v1/applications/` | Save a job |
| PATCH | `/api/v1/applications/{id}` | Update application status |

Full interactive docs at `http://localhost:8000/docs`

---

## 👤 About

Built by **Zoeb Ali Khan**

M.Sc. Data Science · Universität Bielefeld · Expected March 2027

DataCamp Certified: Data Scientist Professional · Data Engineer Associate

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=for-the-badge&logo=linkedin)](https://linkedin.com/in/zoeb-ali-khan)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=for-the-badge&logo=github)](https://github.com/zoeb7184)

---

<div align="center">

⭐ Star this repo if you find it useful

</div>
