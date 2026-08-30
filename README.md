# Skylark BI Agent

A chat-based Business Intelligence agent over two Monday.com boards (Deals and Work Orders). Fetches live data, normalizes it defensively, computes metrics deterministically in Python, and uses Google Gemini only to explain results in business language — never to do arithmetic.

## Architecture

- **FastAPI** backend, no database — conversation state and the fetched-board cache live in Vercel KV / Upstash Redis in production, or in-process memory for local `uvicorn` dev (`app/kv_store.py`).
- **Monday.com** accessed read-only via GraphQL (`app/monday/`), with schema discovery and full cursor pagination.
- **Canonical model** (`app/canonical/`) maps raw Monday columns to a stable internal shape via alias tables, with a narrow type/sample-value fallback for re-labeled boards.
- **Normalization** (`app/normalize/`) — pure functions for dates, numbers, text, and statuses that never guess and never throw.
- **Validation** (`app/validate/`) — drops structurally corrupted rows (header-echo artifacts) before normalization, and builds a per-field data-quality report that treats 0%-filled fields as a structural absence rather than per-record noise.
- **BI engine** (`app/bi/`) — one deterministic function per metric family (pipeline, revenue, operations, sector performance, cross-board, leadership update). All arithmetic lives here; nothing here produces prose.
- **Agent** (`app/agent/`) — Gemini function-calling loop. Python renders the Answer/Key-metrics/Data-quality sections verbatim from typed tool results; Gemini's final turn writes only the Insight prose. See `DECISION_LOG.md` for why.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # then fill in real values
```

Required environment variables (`.env`):

```
MONDAY_API_TOKEN=...
DEALS_BOARD_ID=...
WORK_ORDERS_BOARD_ID=...
GEMINI_API_KEY=...
```

Optional, required only in production (see Deploy below):

```
KV_REST_API_URL=...
KV_REST_API_TOKEN=...
```

## Run locally

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — a minimal chat UI is served from `app/static/`.

## Tests

```bash
pytest tests/ -v
```

Covers normalization edge cases (ambiguous dates, unit-embedded numbers, missing-vs-zero), the header-echo structural-corruption filter, canonical mapping against realistic column shapes, and the BI engine (pipeline/revenue/cross-board) against hand-verifiable fixtures.

## Deploy (Vercel)

`api/index.py` re-exports the FastAPI app from `app/main.py`. `vercel.json` uses the current `functions` + `rewrites` config (not the legacy `builds`/`routes` format) so `maxDuration` can be set directly; Vercel auto-detects `api/index.py` as Python from the root `requirements.txt`, no explicit builder needed. Do not add other files under `api/` — each would become its own isolated function unable to share state with this one.

1. Set `MONDAY_API_TOKEN`, `DEALS_BOARD_ID`, `WORK_ORDERS_BOARD_ID`, `GEMINI_API_KEY` in the Vercel project's environment variables (dashboard, or `vercel env add`) — never in a committed `.env` (`.vercelignore` excludes it from the deployment bundle regardless).
2. Provision a Vercel KV (or Upstash Redis) store and set `KV_REST_API_URL` / `KV_REST_API_TOKEN` the same way. Without these, the board cache and chat session state fall back to in-process memory, which a serverless function does not persist across invocations — every turn would refetch both boards and lose conversation history. See `DECISION_LOG.md`.
3. `vercel.json` sets `maxDuration: 60` on `api/index.py`. **This is only honored on Pro or higher** — on Hobby, Vercel clamps/rejects anything past the 10s default, making that value a no-op. If deploying to Hobby, drop it back to the default and treat the parallelized board fetch + a minimal Gemini tool-calling loop as load-bearing for staying inside 10s, not optional headroom.
4. Test with `vercel dev` before the final deploy, not bare `uvicorn` — `uvicorn` won't surface state that quietly doesn't exist once the function is actually serverless.

## Known limitations

- No database: sessions expire after 1 hour and are never durable beyond that. Without a configured KV store (local `uvicorn` dev, or a Vercel deploy missing `KV_REST_API_URL`/`KV_REST_API_TOKEN`), a process restart or serverless cold start clears all conversation state and the board cache immediately.
- Deals and Work Orders cannot be joined at the individual-record level in the current dev boards (see `DECISION_LOG.md`) — cross-board analysis is sector-aggregated only.
- The board cache has a 2-minute TTL; data is never presented as more current than that.
