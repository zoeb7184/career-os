# Deploying Career OS to Railway

This repo deploys as **five Railway services**: `api` and `frontend` (built
from this repo via Docker), plus `Postgres` and `Redis` (one-click plugins)
and `qdrant` (a Docker Image service, since Railway doesn't have a Qdrant
plugin). The steps below are a **one-time setup** — Railway doesn't support
creating plugins/services from a bare repo with zero dashboard interaction,
so this is the part that can't be scripted. Once it's done, every subsequent
deploy really is one command (`railway up`, `./deploy.sh`, or just `git push`
via the GitHub Action) — see [After setup](#after-setup) at the bottom.

## 1. Create the project

1. Go to <https://railway.app> and sign up / log in with GitHub.
2. **New Project → Deploy from GitHub repo** → select `zoeb7184/career-os`.
3. Railway finds `/railway.json` at the repo root and creates your first
   service (`api`) from it — `DOCKERFILE` builder, `backend/Dockerfile.railway`.
   Rename the service to `api` if Railway named it after the repo.

## 2. Add PostgreSQL and Redis (one click each)

In the project canvas: **+ New → Database → Add PostgreSQL**, then
**+ New → Database → Add Redis**. Nothing to configure — Railway provisions
both and exposes their connection info as service variables.

> **Gotcha:** this app reads `POSTGRES_URL`, but Railway's Postgres plugin
> exposes it as `DATABASE_URL`. Redis's variable is already named
> `REDIS_URL` (no rename needed) — see the variable list in step 4.

## 3. Add Qdrant

**+ New → Empty Service**, then set it to deploy from a Docker image
(**Settings → Source → Docker Image**): `qdrant/qdrant:v1.9.1`. Rename the
service to `qdrant`. Under **Settings → Volumes**, add a volume mounted at
`/qdrant/storage` — without it, every redeploy wipes your embeddings.

## 4. Set environment variables on the `api` service

**api service → Variables**, add (values from your own `.env`, not the
placeholders in `.env.example`):

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `API_PREFIX` | `/api/v1` |
| `CORS_ORIGINS` | your frontend's Railway URL, e.g. `https://career-os-frontend.up.railway.app` (set after step 6 — see note there) |
| `POSTGRES_URL` | `${{Postgres.DATABASE_URL}}` — Railway variable reference, not a literal value |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}` |
| `QDRANT_URL` | `http://qdrant.railway.internal:6333` (adjust the hostname if you named the service something other than `qdrant`) |
| `QDRANT_API_KEY` | leave empty unless you set one on the Qdrant service |
| `JWT_SECRET_KEY` | generate with `openssl rand -hex 32` — do not reuse the dev value |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_MINUTES` | `10080` |
| `GROQ_API_KEY` | from <https://console.groq.com> |
| `GROQ_MODEL_EXTRACTION` | `llama-3.1-8b-instant` |
| `GROQ_MODEL_ADVISOR` | `llama-3.3-70b-versatile` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | optional — job ingestion connector |
| `REED_API_KEY` | optional — job ingestion connector |
| `THE_MUSE_API_KEY` | optional |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional — only if using Google OAuth |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `S3_BUCKET` | optional — only if you wire up resume storage to S3 |

`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` normally use Redis DBs 1/2 in
dev (`docker-compose.yml`); pointing them at the same DB 0 as `REDIS_URL`
is a simplification that's fine at this scale — split them out with
`?` query params if you outgrow it.

Railway auto-detects `/health` from `railway.json`'s `healthcheckPath` — no
action needed there.

## 5. Deploy the frontend

**+ New → GitHub Repo** → same repo again → this time set **Settings → Root
Directory** to `frontend`. Railway picks up `frontend/railway.toml` there
(`DOCKERFILE` builder, `frontend/Dockerfile`). Rename the service to
`frontend`.

Get the `api` service's public URL from **api → Settings → Networking →
Generate Domain** if you haven't already, then on the `frontend` service:

> **Gotcha — this is the one people miss:** `NEXT_PUBLIC_API_URL` gets
> compiled into the client-side JS bundle at *build* time, not read at
> container startup. Add it under **Variables**, then explicitly mark it as
> a **build-time variable** (the toggle next to the variable, or add it
> under **Settings → Build → Build Args**) so it's actually present during
> `npm run build`, not just when the container runs. If you only add it as
> a normal runtime variable, the frontend will silently keep calling
> `http://localhost:8000` from every browser.

```
NEXT_PUBLIC_API_URL=https://<your-api-service>.up.railway.app
```

Generate a public domain for `frontend` too (**Settings → Networking →
Generate Domain**), then go back to the `api` service and set `CORS_ORIGINS`
to that URL (step 4) — the two services' domains are circular, so this is
the order that avoids chasing your tail.

## 6. (Optional but recommended) Add a worker service

The Docker/compose setup runs a Celery worker for background resume
embedding, skill extraction, and ATS scoring queue processing
(`app/workers/*`). Without it, `POST /resumes/upload` and friends still
succeed (they enqueue to Redis and move on), but nothing ever *processes*
those jobs — resumes stay stuck with no embedding, no extracted skills.

To add it: **+ New → GitHub Repo** → same repo → Root Directory `/` →
**Settings → Deploy → Custom Start Command**:
```
celery -A app.workers.celery_app worker --loglevel=info --queues=ats,embeddings,default --concurrency=2
```
It can reuse the exact same env vars as `api` (copy them over, or use
Railway's "Reference variables from another service" if available in your
plan).

## 7. Verify

- `https://<api-domain>/health` → `{"overall": "ok", ...}`
- `https://<frontend-domain>/` → landing page loads, live job count in the
  hero pulls from the real API (confirms `NEXT_PUBLIC_API_URL` baked in
  correctly)
- Register an account, upload a resume, run an ATS score — exercises
  Postgres, Redis, Qdrant, and Groq all in one pass.

---

## After setup

Once the five services above exist, you don't need the dashboard again for
routine deploys:

- **CLI, one command:** `./deploy.sh` (installs the Railway CLI if needed,
  logs in, links the project, deploys `api` then `frontend`).
- **Automatic on push:** merge to `main` — `.github/workflows/deploy.yml`
  redeploys both services after CI passes, using a `RAILWAY_TOKEN` repo
  secret (**Railway → Account Settings → Tokens**, then add it at
  **GitHub repo → Settings → Secrets and variables → Actions**).
- **Local prod-parity check** before either of those, if you want it:
  `docker compose -f docker-compose.prod.yml up --build` runs the exact
  same images against local Postgres/Redis/Qdrant containers instead of
  Railway's.

## Troubleshooting

- **`/health` reports `degraded` or a node as `error`:** check that service's
  entry in the JSON response — `postgres`/`redis`/`qdrant` failing usually
  means a `${{Service.VAR}}` reference is wrong (typo'd service name, or it
  hasn't finished provisioning yet). Adzuna/Reed showing `not_started` is
  normal if you left those keys blank.
- **Frontend loads but every API call fails as a network error:** almost
  always the `NEXT_PUBLIC_API_URL` build-time-vs-runtime gotcha from step 5.
  Fix the variable, then trigger a fresh deploy (redeploying without a
  rebuild reuses the old baked-in value).
- **CORS errors in the browser console:** `CORS_ORIGINS` on `api` doesn't
  exactly match the frontend's URL (scheme + host, no trailing slash).
- **Resumes upload but never get an ATS score / skills:** you skipped step
  6 — there's no worker consuming the queue.
