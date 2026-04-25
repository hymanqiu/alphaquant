# AlphaQuant — common dev tasks.
#
# Run `make help` for the menu. Targets that need the venv automatically
# activate backend/.venv first.

PYTHON ?= python3
BACKEND := backend
FRONTEND := frontend
VENV := $(BACKEND)/.venv
ACTIVATE := . $(VENV)/bin/activate

# Defaulting to "help" instead of "all" so a bare `make` doesn't blow anything up.
.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this menu
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---- one-shot bootstrap ------------------------------------------------------

.PHONY: setup
setup:  ## One-command developer bootstrap (Postgres + venv + deps + migrations)
	./scripts/dev-setup.sh

# ---- infrastructure ----------------------------------------------------------

.PHONY: db-up
db-up:  ## Start the local Postgres container
	docker compose up -d postgres

.PHONY: db-down
db-down:  ## Stop Postgres but keep data
	docker compose down

.PHONY: db-wipe
db-wipe:  ## Stop Postgres AND wipe its data volume (destructive)
	docker compose down -v

.PHONY: db-shell
db-shell:  ## psql shell into the dev database
	docker exec -it alphaquant-postgres psql -U alpha -d alphaquant

# ---- migrations --------------------------------------------------------------

.PHONY: migrate
migrate:  ## Apply all pending Alembic migrations
	cd $(BACKEND) && $(ACTIVATE) && alembic upgrade head

.PHONY: migrate-down
migrate-down:  ## Roll back one migration (use with care)
	cd $(BACKEND) && $(ACTIVATE) && alembic downgrade -1

.PHONY: migrate-new
migrate-new:  ## Autogenerate a new migration. Usage: make migrate-new MSG="add foo"
	@if [ -z "$(MSG)" ]; then echo "MSG=... is required"; exit 1; fi
	cd $(BACKEND) && $(ACTIVATE) && alembic revision --autogenerate -m "$(MSG)"

# ---- run servers -------------------------------------------------------------

.PHONY: backend
backend:  ## Start the FastAPI backend on :8000 (auto-reload)
	cd $(BACKEND) && $(ACTIVATE) && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

.PHONY: frontend
frontend:  ## Start the Next.js dev server on :3000
	cd $(FRONTEND) && npm run dev

.PHONY: dev
dev:  ## Start backend + frontend in parallel (Ctrl-C stops both)
	@echo "Starting backend on :8000 and frontend on :3000…"
	@$(MAKE) -j 2 backend frontend

# ---- tests + lint ------------------------------------------------------------

.PHONY: test
test:  ## Run backend pytest suite
	cd $(BACKEND) && $(ACTIVATE) && pytest -q

.PHONY: typecheck
typecheck:  ## Run frontend TypeScript check
	cd $(FRONTEND) && npx tsc --noEmit

.PHONY: lint
lint: typecheck  ## Run all available linters

# ---- admin convenience -------------------------------------------------------

.PHONY: promote
promote:  ## Manually promote an email to Pro tier. Usage: make promote EMAIL=foo@bar.com
	@if [ -z "$(EMAIL)" ]; then echo "EMAIL=... is required"; exit 1; fi
	@if [ -z "$$AQ_ADMIN_TOKEN" ]; then \
		echo "Loading AQ_ADMIN_TOKEN from backend/.env"; \
		AQ_ADMIN_TOKEN=$$(grep '^AQ_ADMIN_TOKEN=' $(BACKEND)/.env | cut -d= -f2-); \
	fi; \
	curl -sS -X PATCH \
	  -H "Authorization: Bearer $$AQ_ADMIN_TOKEN" \
	  -H "Content-Type: application/json" \
	  -d '{"tier":"pro"}' \
	  "http://localhost:8000/api/admin/users/$(EMAIL)/tier" | python3 -m json.tool

.PHONY: usage
usage:  ## Show the last 24h LLM usage + rate-limit snapshot
	@AQ_ADMIN_TOKEN=$$(grep '^AQ_ADMIN_TOKEN=' $(BACKEND)/.env | cut -d= -f2-); \
	curl -sS -H "Authorization: Bearer $$AQ_ADMIN_TOKEN" \
	  http://localhost:8000/api/admin/usage | python3 -m json.tool
