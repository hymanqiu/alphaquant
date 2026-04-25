#!/usr/bin/env bash
#
# One-command bootstrap for local development.
#
#   1. Verifies prerequisites (python, node, docker)
#   2. Starts Postgres via docker compose (if not running)
#   3. Creates Python venv, installs backend deps
#   4. Installs frontend deps
#   5. Bootstraps backend/.env from .env.example if missing
#   6. Applies Alembic migrations
#
# Usage:  ./scripts/dev-setup.sh
#
# Run once on a fresh checkout. Re-run anytime to ensure the dev environment
# matches the repo state — it is idempotent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- pretty logging ---------------------------------------------------------
GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; BOLD="\033[1m"; RESET="\033[0m"
step()   { printf "${BOLD}${GREEN}==>${RESET} %s\n" "$*"; }
warn()   { printf "${BOLD}${YELLOW}!! ${RESET} %s\n" "$*"; }
fail()   { printf "${BOLD}${RED}xx ${RESET} %s\n" "$*" >&2; exit 1; }

# ---- 1. prerequisites -------------------------------------------------------
step "Checking prerequisites"
command -v python3 >/dev/null || fail "python3 not found (need >=3.10)"
command -v node    >/dev/null || fail "node not found (need >=20)"
command -v docker  >/dev/null || fail "docker not found"

# `docker compose` (v2) preferred; fall back to legacy `docker-compose`.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  fail "docker compose plugin not found"
fi

# ---- 2. Postgres ------------------------------------------------------------
step "Starting Postgres (docker compose)"
$COMPOSE up -d postgres

# Wait for Postgres healthcheck to pass.
step "Waiting for Postgres to accept connections..."
for i in $(seq 1 30); do
  if docker exec alphaquant-postgres pg_isready -U alpha -d alphaquant >/dev/null 2>&1; then
    echo "   Postgres is ready."
    break
  fi
  if [[ $i -eq 30 ]]; then
    fail "Postgres did not become ready within 30s. Check 'docker compose logs postgres'."
  fi
  sleep 1
done

# ---- 3. backend env ---------------------------------------------------------
step "Bootstrapping backend/.env"
if [[ ! -f "$REPO_ROOT/backend/.env" ]]; then
  if [[ -f "$REPO_ROOT/backend/.env.example" ]]; then
    cp "$REPO_ROOT/backend/.env.example" "$REPO_ROOT/backend/.env"
    warn "Created backend/.env from .env.example. Fill in API keys before running."
  else
    fail "backend/.env.example missing — cannot bootstrap"
  fi
else
  echo "   backend/.env already exists; leaving it alone."
fi

# ---- 4. Python venv + deps --------------------------------------------------
step "Setting up Python venv + deps"
cd "$REPO_ROOT/backend"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -e ".[dev]"

# ---- 5. Alembic migrations --------------------------------------------------
step "Applying database migrations (alembic upgrade head)"
alembic upgrade head

# ---- 6. Frontend deps -------------------------------------------------------
step "Installing frontend deps"
cd "$REPO_ROOT/frontend"
if [[ -f "package-lock.json" ]]; then
  npm ci
else
  npm install
fi

# ---- done -------------------------------------------------------------------
cat <<EOF

${BOLD}${GREEN}Setup complete.${RESET}

Next steps:

  1. Edit backend/.env and fill in:
       - AQ_LLM_API_KEY              (DeepSeek key, required for LLM features)
       - AQ_FMP_API_KEY              (already provisioned; verify still valid)
       - AQ_GOOGLE_OAUTH_CLIENT_ID*  (optional; only needed for Google sign-in)
       - AQ_RESEND_API_KEY           (optional; without it, magic links print to stderr)

  2. Run the dev servers:
       make dev          # one-shot: backend + frontend
                         # (or run them in two terminals manually:)
       cd backend  && source .venv/bin/activate && uvicorn backend.main:app --reload
       cd frontend && npm run dev

  3. Open http://localhost:3000 and try /analyze/AAPL.

EOF
