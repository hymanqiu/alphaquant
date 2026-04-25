# Development Guide

Onboarding for new contributors. Read this once, then keep [ARCHITECTURE.md](ARCHITECTURE.md) and [CHANGELOG.md](CHANGELOG.md) handy.

---

## 1. Prerequisites

| Tool | Min version | Why |
|------|-------------|-----|
| Python | 3.10 | Backend runtime |
| Node.js | 20 | Frontend (Next.js 16) |
| Docker + Docker Compose v2 | latest | Local Postgres |
| `make` | any | Optional but every command in this doc has a Make target |

You also need three external API keys (see [Section 4](#4-external-services--api-keys)):
- **DeepSeek** (or any OpenAI-compatible LLM) — required for any LLM feature
- **Financial Modeling Prep (FMP)** — required for prices / peers
- **Finnhub** — optional, for news

---

## 2. First-time setup (one command)

```bash
git clone <repo> alpha && cd alpha
make setup
```

`make setup` runs [scripts/dev-setup.sh](scripts/dev-setup.sh), which is **idempotent** — re-run it anytime to bring your environment back in sync. It does:

1. Verifies prerequisites
2. Starts Postgres via `docker compose up -d postgres`
3. Creates `backend/.venv`, installs Python deps in editable mode
4. Copies `backend/.env.example` → `backend/.env` if missing
5. Runs `alembic upgrade head` to create the schema
6. Installs frontend deps with `npm ci`

After it finishes, **edit `backend/.env`** and at minimum fill `AQ_LLM_API_KEY` and `AQ_FMP_API_KEY`. See [Section 4](#4-external-services--api-keys).

---

## 3. Daily workflow

```bash
make dev          # backend (:8000) + frontend (:3000) in parallel; Ctrl-C stops both
```

Or run them in separate terminals:

```bash
make backend
make frontend
```

Open <http://localhost:3000>, type a ticker (e.g. `AAPL`), and watch the SSE stream populate the analysis cards.

### Common tasks

| Command | What it does |
|---------|--------------|
| `make help` | Show every Make target |
| `make db-up` / `db-down` / `db-wipe` | Start / stop / wipe local Postgres (`-v` flag wipes the volume) |
| `make db-shell` | Drop into `psql` against the dev DB |
| `make migrate` | Apply all pending migrations |
| `make migrate-new MSG="add foo"` | Autogenerate a new Alembic revision from ORM changes |
| `make migrate-down` | Roll back one migration |
| `make test` | Run backend pytest |
| `make typecheck` | Run frontend `tsc --noEmit` |
| `make promote EMAIL=foo@bar.com` | Manually promote a registered user to Pro tier |
| `make usage` | Snapshot of LLM spend + rate-limit hits over last 24h |

---

## 4. External services / API keys

| Variable | How to get | Required? |
|----------|------------|-----------|
| `AQ_LLM_API_KEY` | <https://platform.deepseek.com/api_keys> | **Yes** for any LLM feature |
| `AQ_FMP_API_KEY` | <https://site.financialmodelingprep.com> (free tier 5 req/min) | **Yes** for prices / peers |
| `AQ_FINNHUB_API_KEY` | <https://finnhub.io/dashboard> (free tier 60 req/min) | Optional — without it, news is empty |
| `AQ_RESEND_API_KEY` | <https://resend.com/api-keys> | Optional — magic links print to stderr without it |
| `AQ_GOOGLE_OAUTH_*` | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client (Web) | Optional — only for Google sign-in |
| `AQ_ADMIN_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | Optional but recommended in any deploy |
| `AQ_JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | **Yes** for auth — empty disables auth entirely |
| `AQ_MAGIC_LINK_SECRET` | same as above | Required only for magic-link sign-in |

> **Heads up:** `backend/.env` is gitignored. Never commit secrets.

### Google OAuth setup notes

When configuring the OAuth client in Google Cloud Console:

1. Application type: **Web application**
2. Authorized redirect URIs: `http://localhost:8000/api/auth/google/callback` (dev) and your production callback
3. Scopes are requested at runtime (`openid email profile`); you do NOT need to enable "OAuth consent screen" for testing inside the same Google Workspace.

---

## 5. Project layout (high level)

See [ARCHITECTURE.md §2](ARCHITECTURE.md#2-directory-structure) for the full tree. Quick reference:

```
alpha/
├── docker-compose.yml      # Postgres for local dev
├── Makefile                # Every dev command lives here
├── scripts/dev-setup.sh    # First-time bootstrap
├── DEVELOPMENT.md          # ← you are here
├── ARCHITECTURE.md         # System design, data flow, every node
├── CHANGELOG.md            # Per-version migration notes
├── backend/
│   ├── alembic/            # Migration scripts
│   ├── backend/
│   │   ├── api/            # FastAPI routes (analyze, recalculate, auth, admin)
│   │   ├── agents/         # LangGraph nodes — one file per analysis step
│   │   ├── prompts/        # YAML prompt templates (versioned)
│   │   ├── services/
│   │   │   ├── auth/       # User model + 3 auth providers + JWT + tier gating
│   │   │   ├── llm/        # Unified LLMClient + budget gate + token accounting
│   │   │   ├── db.py       # Async SQLAlchemy engine
│   │   │   ├── rate_limit.py
│   │   │   └── runtime_settings.py
│   │   └── models/         # Pydantic + LangGraph state types
│   └── tests/
└── frontend/
    └── src/
        ├── app/            # Next.js App Router pages (auth/, analyze/[ticker]/)
        ├── components/
        │   ├── analysis/   # 18 cards (12 free + 4 Pro + 1 locked + 1 shared)
        │   └── component-registry.ts  # SSE component_type → React component
        ├── context/        # AuthProvider + HistoryProvider
        ├── hooks/          # useSSE + useAnalysisStream
        └── lib/            # auth-api / types / utils
```

---

## 6. The 12-node analysis pipeline

Every `/analyze/{ticker}` request walks this DAG sequentially. Each node emits SSE events as it runs.

```
1.  fetch_sec_data            (SEC EDGAR XBRL)
2.  financial_health_scan     (debt / margin / ROE)
3.  dynamic_dcf               (2-stage DCF)
4.  relative_valuation        (FMP peer multiples)
5.  event_sentiment           (Finnhub news + LLM scoring)         [LLM]
6.  event_impact              (2 LLM calls → DCF param adjustment) [LLM]
7.  strategy                  (margin of safety + signal)
8.  qualitative_analysis      (10-K MD&A + Risk Factors)           [LLM, Pro]
9.  risk_yoy_diff             (this year vs. last year 10-K)       [LLM, Pro]
10. moat_analysis             (Helmer 7 Powers scoring)            [LLM, Pro]
11. investment_thesis         (synthesized research narrative)     [LLM, Pro]
12. logic_trace               (data lineage to SEC accessions)
```

Pro nodes (8 / 9 / 10 / 11) emit a "locked preview" component for free-tier users — see [ARCHITECTURE.md §Phase 2](ARCHITECTURE.md#phase-2-auth--tier-gating).

LLM nodes are tied to the global + per-IP **budget gate** (Phase 1). When the day's budget is exhausted, every LLM call raises `LLMBudgetExceeded` and the Pro nodes degrade like a normal LLM error.

---

## 7. Adding a new analysis node

The pattern is well-established. To add another, e.g. `dividend_safety_analysis`:

1. **Prompt YAML** — `backend/backend/prompts/dividend_safety_v1.yaml` with strict system prompt + verbatim quote rule.
2. **Node** — `backend/backend/agents/nodes/dividend_safety.py` — define a Pydantic response model, write the async node function. Use `LLMClient.complete_json(prompt_name=..., response_model=...)` and `verify_quotes()` for any extracted quotes.
3. **State** — add a new field to `AnalysisState` in `models/agent_state.py` and to the `initial_state` dict in `api/routes.py`.
4. **Graph** — register in `agents/value_analyst.py` (add node + edge).
5. **Frontend card** — `frontend/src/components/analysis/dividend-safety-card.tsx`. Register it in `component-registry.ts` keyed by the `component_type` your node emits.
6. **Pipeline step label** — add an entry in `frontend/src/hooks/use-analysis-stream.ts` so the UI displays a friendly progress label.
7. **(Optional) Pro gate** — if the node should be Pro-only, import `_pro_gate.is_pro_user` and `emit_lock` and short-circuit at the top of the node. Register a `dividend_safety_locked_card` mapping to `pro-locked-card.tsx` in the registry.

A great template to copy: `backend/backend/agents/nodes/moat_analysis.py` + `frontend/src/components/analysis/moat-analysis-card.tsx`.

---

## 8. Adding a new auth provider

The auth module is intentionally pluggable. Each provider is a self-contained Python module under `backend/backend/services/auth/`. All flows funnel into `AuthService.upsert_<provider>_user(...)` which handles user lookup / linkage / `last_login_at` bookkeeping.

To add e.g. GitHub OAuth:

1. Create `services/auth/github_oauth.py` mirroring `google_oauth.py` (authlib OAuth client + `is_configured()`).
2. Add `register_github_user(github_id, email, ...)` to `AuthService` if the user-resolution logic differs (or just reuse `upsert_google_user`'s pattern).
3. Add config keys (`AQ_GITHUB_OAUTH_CLIENT_ID` / `_SECRET` / `_REDIRECT_URL`) in `config.py`, `.env.example`, and `.env`.
4. Add `/api/auth/github/start` and `/api/auth/github/callback` routes in `api/auth.py`.
5. Add a "Sign in with GitHub" button to `app/auth/login/page.tsx`.

No changes to the database schema needed — the `identity_providers` table already supports any `kind` string (the CHECK constraint will need a one-line migration to allow the new value).

---

## 9. Cost / safety guardrails

The system protects against runaway costs in three layers:

1. **IP rate limit** (`services/rate_limit.py`) — 3 analyses / IP / 24h on `/analyze`, configurable via admin API.
2. **Per-IP LLM budget** — single IP can't spend > $0.25/day in LLM costs by default.
3. **Global LLM budget** — daily spend cap (default $5/day). When tripped, every Pro node degrades for everyone until midnight.

All three are runtime-adjustable through the admin API:

```bash
make usage                                                          # see current spend
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"llm_daily_budget_usd": 20.0}' \
  http://localhost:8000/api/admin/settings                          # raise to $20
```

---

## 10. Troubleshooting

**Postgres won't start.** Check `docker compose logs postgres`. Common cause: another Postgres on `:5432`. Either stop it or change the port in `docker-compose.yml` and `AQ_DATABASE_URL`.

**`alembic upgrade head` fails with "DSN missing".** `backend/.env` isn't loaded — make sure you ran the command from inside `backend/` after `source .venv/bin/activate`. `make migrate` does this automatically.

**Magic-link emails never arrive.** If `AQ_RESEND_API_KEY` is empty, the link is logged to backend stderr and returned as `dev_link` in the API response. Check the login form's "magic link" tab — the dev fallback link appears there too.

**Google OAuth returns "redirect_uri_mismatch".** The redirect URI in your Google Cloud Console OAuth client must match `AQ_GOOGLE_OAUTH_REDIRECT_URL` byte-for-byte (including the port).

**Frontend shows 401 Unauthorized for /api/auth/me.** Expected — that's the anonymous state. The `AuthProvider` swallows this and treats it as `status="anonymous"`.

**`/analyze` returns 429.** The per-IP rate limit (default 3/day). Either wait, raise the limit (`make usage` then PATCH), or come from a different IP.

**LLM features all show "skipped" or "Pro-only".** Either `AQ_LLM_API_KEY` is empty, the user is on free tier, or the budget tripped. Check `make usage`.

---

## 11. Where to read more

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, full pipeline, every node's contract
- [CHANGELOG.md](CHANGELOG.md) — version-by-version diff
- [MVP-GAP.html](MVP-GAP.html) — open work items toward commercial MVP
- [backend/.env.example](backend/.env.example) — every config knob with explanation
