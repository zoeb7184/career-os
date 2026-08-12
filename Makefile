# ─────────────────────────────────────────────────────────────────
#  Career OS — Makefile
#  Usage: make <command>
#  All commands work from the project root.
# ─────────────────────────────────────────────────────────────────

.PHONY: help dev down logs health test test-node lint format migrate reset-db shell ps

# ── Default: show help ─────────────────────────────────────────────
help:
	@echo ""
	@echo "  Career OS — Available Commands"
	@echo "  ─────────────────────────────────────────"
	@echo "  make dev          Start all containers (hot reload)"
	@echo "  make down         Stop all containers"
	@echo "  make ps           Show container status"
	@echo "  make logs         Tail all logs"
	@echo "  make logs N=api   Tail one container's logs"
	@echo "  make health       Check all node health"
	@echo "  make test         Run all tests"
	@echo "  make test-node N=ats_analyzer   Run one node's tests"
	@echo "  make lint         Run ruff + mypy"
	@echo "  make format       Auto-format with ruff"
	@echo "  make migrate      Run Alembic migrations"
	@echo "  make reset-db     DROP and recreate all tables (dev only!)"
	@echo "  make shell        Open Python shell with app context"
	@echo ""

# ── Docker ─────────────────────────────────────────────────────────
dev:
	docker compose up --build -d
	@echo "✅ All containers starting..."
	@echo "   API:     http://localhost:8000"
	@echo "   Docs:    http://localhost:8000/docs"
	@echo "   Health:  http://localhost:8000/health"
	@echo "   MLflow:  http://localhost:5000"
	@echo "   Qdrant:  http://localhost:6333/dashboard"

down:
	docker compose down

ps:
	docker compose ps

logs:
ifdef N
	docker logs career-os-$(N) -f --tail=100
else
	docker compose logs -f --tail=50
endif

# ── Health check ───────────────────────────────────────────────────
health:
	@echo "Checking all nodes..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "❌ API unreachable"

# ── Testing ────────────────────────────────────────────────────────
test:
	docker exec career-os-api pytest /app/tests/ /pkgs/ml/ -v --tb=short 2>&1

test-node:
ifdef N
	docker exec career-os-api pytest /pkgs/ml/$(N)/tests/ -v --tb=short 2>&1
else
	@echo "Usage: make test-node N=ats_analyzer"
endif

# ── Code quality ───────────────────────────────────────────────────
lint:
	cd backend && ruff check . && mypy app/ --ignore-missing-imports
	@echo "✅ Lint passed"

format:
	cd backend && ruff format .
	@echo "✅ Formatted"

# ── Database ───────────────────────────────────────────────────────
migrate:
	docker exec career-os-api alembic upgrade head
	@echo "✅ Migrations applied"

reset-db:
	@echo "⚠️  This will DELETE all data. Press Ctrl+C to cancel, Enter to continue."
	@read confirm
	docker exec career-os-postgres psql -U career_user -d career_os -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker exec career-os-api alembic upgrade head
	@echo "✅ Database reset"

# ── Dev shell ──────────────────────────────────────────────────────
shell:
	docker exec -it career-os-api python3

seed:
	docker exec career-os-api python -m app.scripts.seed_skills
	@echo "✅ Skills seeded"

ingest:
	docker exec career-os-api python -m data_pipeline.flows.ingestion_flow
	@echo "✅ Ingestion complete"

snapshot:
	docker exec career-os-api python -m data_pipeline.flows.snapshot_flow
	@echo "✅ Market snapshot complete"

setup: migrate seed
	@echo "✅ Database ready"
