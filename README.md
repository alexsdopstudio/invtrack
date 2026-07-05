# InvTrack — personal stock research dashboard

InvTrack aggregates **free, public data sources** — congressional trading
disclosures (STOCK Act), SEC EDGAR Form 4 insider trades, and
fundamentals/prices — into a single dashboard with a configurable composite
signal score (0–100) per ticker, with full provenance for every number.

> ## ⚠️ Disclaimer
> InvTrack is a **personal research aid, not financial advice**. It never
> issues buy/sell recommendations. Congressional trading disclosures are
> **legally delayed by up to 45 days**, so every congressional signal is
> lagging by design. The Senate/House Stock Watcher datasets are
> community-maintained — verify any signal you care about against the
> official sources ([efdsearch.senate.gov](https://efdsearch.senate.gov),
> [disclosures-clerk.house.gov](https://disclosures-clerk.house.gov),
> [sec.gov](https://www.sec.gov)) before acting on it.

## Architecture

- **Backend** — FastAPI + SQLAlchemy 2 + Alembic (`backend/`). Ingestion jobs
  are idempotent, isolated per source (one broken source never blocks the
  rest), and every run is recorded in an `ingestion_run` audit table. Every
  fact row keeps its raw source payload (bronze layer) for provenance.
- **Database** — Postgres (Supabase) in production, SQLite for zero-setup
  local development. Controlled entirely by `DATABASE_URL`.
- **Frontend** — Vite + React + TypeScript + Tailwind (`frontend/`), with a
  persistent disclaimer banner, a watchlist dashboard, and a per-ticker
  detail page that explains exactly why a score is what it is.

### Data sources (all free)

| Signal | Source | Notes |
|---|---|---|
| Ticker ↔ CIK map | [SEC company_tickers.json](https://www.sec.gov/files/company_tickers.json) | official |
| Senate trades | official [efdsearch.senate.gov](https://efdsearch.senate.gov) PTRs | electronic filings parsed directly from the Senate's search system; lagging ≤45 days by law |
| House trades | Stock Watcher-shaped JSON via `HOUSE_DATA_URL` | original community bucket defunct (July 2026); official House PTRs are PDFs — see note below |
| Insider trades (Form 4) | SEC EDGAR (`data.sec.gov` submissions + Form 4 XML) | official, filed within 2 business days |
| Fundamentals & prices | yfinance | unofficial; failures isolated per ticker |

The SEC asks automated clients to identify themselves — set
`SEC_EDGAR_USER_AGENT` to your name + email. Requests to sec.gov are
throttled well below their 10 req/s guidance.

## Quick start (local, SQLite, no keys)

```bash
# backend
cd backend
./setup.sh                            # creates .venv pinned to public PyPI (ignores corporate pip config)
cp ../.env.example ../.env            # edit SEC_EDGAR_USER_AGENT
.venv/bin/alembic upgrade head        # create the schema
.venv/bin/python -m app.cli seed-demo # optional: synthetic demo data, no network
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173, proxies /api to :8000
```

Working on a machine with corporate package registries (CodeArtifact,
Artifactory, …)? This project stays isolated from them: `backend/setup.sh`
writes a venv-scoped `pip.conf` pinned to public PyPI (and installs with the
index pinned on the command line, which overrides env vars too), and
`frontend/.npmrc` pins npm to the public registry. The only remaining
gotcha is a globally exported `PIP_INDEX_URL`/`PIP_EXTRA_INDEX_URL` in your
shell profile — that would override the venv config on later manual
`pip install` runs, so unset it or scope it to work directories.

## Using Supabase

1. Create a Supabase project and copy the **Session pooler** connection
   string (Dashboard → Project Settings → Database).
2. In `.env`, set
   `DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. `cd backend && .venv/bin/alembic upgrade head` — the schema (JSONB
   included) is created on Supabase. Everything else is identical.

## Ingesting real data

```bash
cd backend
.venv/bin/python -m app.cli ingest tickers   # SEC ticker/CIK map (~10k rows) — run once first
# add tickers to your watchlist (via the UI or POST /api/watchlist), then:
.venv/bin/python -m app.cli ingest all       # congress + insider + fundamentals + prices, then rescores
```

Or from the UI/API: `POST /api/ingest/all`. Each run is logged —
`GET /api/ingest/runs` (or the UI's refresh status) shows per-source
status/errors. Ingestion is failure-isolated at every level: chambers,
tickers and individual filings are ingested independently, so e.g. the
Senate dataset going offline still lets House trades land.

> **Congressional source status (July 2026):** the community Stock Watcher
> projects are dead, so **senate trades are now ingested from the official
> efdsearch.senate.gov directly** — session/CSRF handshake, paged PTR search
> over the lookback window, and per-report HTML table parsing (paper filings
> are scanned images and skipped). **House trades remain without a live free
> source**: official House PTRs are PDFs on disclosures-clerk.house.gov and
> need a dedicated PDF parser (roadmap). Until then the house side reports an
> error in the run log, the senate side still lands, and if both chambers are
> ever empty the composite score renormalizes over insider + fundamentals. If
> you find a live Stock Watcher-shaped mirror for house data, set
> `HOUSE_DATA_URL` in `.env`. Ingestion only pulls congress/insider/fundamentals/prices for
tickers on your watchlist to stay well inside free-tier rate limits.
Re-run `ingest all` on whatever cadence you like (e.g. a daily cron) — jobs
are idempotent.

## Composite score

Weights and thresholds live in [`backend/scoring.yaml`](backend/scoring.yaml)
— tune them freely; this is a research aid, not a black box.

- **Fundamentals (0.40)** — banded sub-scores for revenue growth, operating
  margin, debt/equity, P/E.
- **Congress (0.35)** — recency-decayed net dollar flow of congressional
  buys vs sells (decay on *disclosure* date, because the data is lagging),
  plus a bonus when ≥3 members trade the same direction within 30 days.
- **Insider (0.25)** — Form 4 open-market buys minus discounted sells
  (insider selling is noisy; buying is the signal), with a multi-insider
  cluster bonus.

If a component has no data its weight is renormalized across the components
that do, and the stored breakdown marks it `missing` — a score is never
silently dragged down by an empty source. Every score row stores the full
per-component breakdown (value, weight, contribution, inputs, source, data
timestamps) so the UI can always answer "why is this score what it is?".

## Screener

The **Screener** page runs every tracked + Radar ticker through an
aggressive-growth quantitative filter (thresholds in
[`backend/scoring.yaml`](backend/scoring.yaml) under `screener:`): market cap
$50M–$2B, avg daily volume ≥150k, revenue growth ≥25%, gross margin ≥60%,
current ratio ≥1.5, cash runway ≥4 quarters, insider ownership ≥10%. All
inputs come from free sources (yfinance + ingested prices); a criterion with
no data reports **unknown**, never a silent verdict. Congress-sourced
candidates are mostly mega-caps and will fail the size criterion — that's the
filter working as intended.

## AI filing analysis (optional, paid)

With `ANTHROPIC_API_KEY` set in `.env`, every ticker page (and the screener)
gets an **"Analyze latest 10-K"** button: InvTrack pulls Items 1 / 1A / 7 of
the company's latest 10-K from SEC EDGAR (free, official) and has Claude write
a forensic-accountant-style review — customer concentration, litigation,
going-concern language, moat quality, management tone — with a "what to verify
next" list. The model never computes financial numbers (those come from the
structured pipeline) and every report carries its model, filing accession and
date. Reports are cached per filing, so cost is ~$0.25–0.50 per *new* 10-K
analyzed (Opus 4.8; configurable via `ANALYSIS_MODEL`). Leave the key unset
and the feature is fully disabled — everything else stays free.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests
```

## Roadmap (from the project spec, not yet built)

Reddit/VADER sentiment, GDELT news, FRED macro context, alerting
(webhook/Telegram), APScheduler-based scheduled ingestion, portfolio-level
concentration checks, position-sizing helper.
