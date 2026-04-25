# AlphaQuant

White-box AI investment research. SEC EDGAR XBRL → 12-node LangGraph value-analysis pipeline → real-time generative UI over SSE.

## Quickstart

```bash
git clone <repo> alpha && cd alpha
make setup          # Postgres + Python venv + npm deps + DB migration (idempotent)
# edit backend/.env to fill AQ_LLM_API_KEY and AQ_FMP_API_KEY
make dev            # backend on :8000, frontend on :3000
```

Open <http://localhost:3000>, type `AAPL`, watch the SSE stream paint cards.

For prerequisites, env-var reference, common tasks, and troubleshooting see **[DEVELOPMENT.md](DEVELOPMENT.md)**.

## What it does

| Layer | Outcome |
|-------|---------|
| **SEC + Market data** | Pulls 10-Ks (XBRL JSON + raw HTML), prices, peer multiples, news |
| **Numeric analysis** (free tier) | Financial health · 2-stage DCF · relative valuation · event-impact-adjusted DCF · margin-of-safety strategy |
| **LLM Pro analysis** (gated) | Investment thesis · 10-K MD&A insights · Risk Factor extraction · YoY risk diff · Helmer 7-Powers moat scoring |
| **Operational guards** | Per-IP rate limit · per-IP & global LLM budget · admin runtime knobs |

Every LLM-extracted quote is verified verbatim against the source filing — hallucinated quotes are auto-dropped before reaching the UI. See [ARCHITECTURE.md §12.3](ARCHITECTURE.md#123-防幻觉机制共三层).

## Repo layout

```
alpha/
├── docker-compose.yml      Postgres for local dev
├── Makefile                make help — every dev command
├── scripts/dev-setup.sh    Idempotent bootstrap
├── DEVELOPMENT.md          ← Start here as a new contributor
├── ARCHITECTURE.md         System design + per-node contracts (long, but searchable)
├── CHANGELOG.md            Version-by-version migration notes
├── MVP-GAP.html            Open commercial-MVP work items
├── backend/                FastAPI + LangGraph + Postgres + Auth
└── frontend/               Next.js 16 SPA with SSE-driven Generative UI
```

## Documentation map

| Doc | Audience | What's in it |
|-----|----------|--------------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Anyone running the project locally | Prereqs, setup, daily commands, env-var reference, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Contributors making architectural decisions | Full data-flow, every node's contract, the 3 cost-guardrail layers, the auth flow |
| [CHANGELOG.md](CHANGELOG.md) | Anyone catching up | Version-by-version: what changed, files added, validation done |
| [backend/.env.example](backend/.env.example) | Anyone configuring | Every config knob with explanation |
| [MVP-GAP.html](MVP-GAP.html) | Product / planning | Outstanding work to reach commercial MVP |

## High-level pipeline (12 nodes)

```
fetch_sec_data → financial_health_scan → dynamic_dcf → relative_valuation
              → event_sentiment [LLM] → event_impact [2× LLM]
              → strategy
              → qualitative_analysis [2× LLM, Pro]   (MD&A + Risk Factors in parallel)
              → risk_yoy_diff [LLM, Pro]             (this year vs. last year 10-K)
              → moat_analysis [LLM, Pro]             (Hamilton Helmer 7 Powers)
              → investment_thesis [LLM, Pro]         (synthesized research narrative)
              → logic_trace
```

Free tier sees the first 7 nodes plus locked-preview cards for the 4 Pro nodes; Pro tier gets all 12.

## Stack

- **Backend**: FastAPI · LangGraph · SQLAlchemy 2.0 (async) + Postgres · Alembic · authlib (Google OAuth) · bcrypt + JWT (HS256) · itsdangerous (magic links) · httpx · BeautifulSoup4 (10-K parsing)
- **Frontend**: Next.js 16 (App Router) · React 19 · Tailwind · Radix UI primitives · lucide-react · recharts
- **Infra**: docker-compose for local Postgres; Resend (optional) for transactional email

## License

Proprietary, all rights reserved.
