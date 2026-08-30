# Skylark BI Agent

Skylark Drones runs its business on two Monday.com boards: Deals and Work Orders. Anyone who wants to know "how's our pipeline looking" or "which sectors are we actually delivering on" has to open Monday, filter, scroll, and do the math by hand. This is a chat agent that does that instead — you ask a plain-English question, it pulls the live boards, computes the real numbers, and answers like a person would.

The one rule I held myself to: **the LLM never does arithmetic.** Every number you see was computed in Python from the actual board data. Gemini's only job is to read those numbers and explain what they mean in plain business language.

For the reasoning behind the non-obvious calls (why sector-only cross-board comparison, why this deploy target, what I'd change with more time, how I read "leadership updates") see `DECISION_LOG.md`. This file covers architecture and how to run it.

## How it works, end to end

1. You ask something like *"what's our open pipeline in Renewables?"*
2. The agent figures out which of six BI tools answers that (pipeline, revenue, operations, sector performance, cross-board, or leadership update) and what filters apply.
3. That tool runs against data already fetched and cleaned from Monday: schema discovered dynamically, junk rows dropped, values normalized, everything mapped into a stable internal shape.
4. The tool returns exact numbers plus whatever caveats matter ("12 of 41 deals have no value on file"). Python renders the Answer, Key Metrics, and Data Quality sections straight from that — no LLM involved.
5. Gemini writes one short paragraph explaining what the numbers mean for the business. That's it — it doesn't get to touch the figures.

## Architecture

- **FastAPI** backend, no database — conversation state and the fetched-board cache live in Vercel KV / Upstash Redis in production, or in-process memory for local `uvicorn` dev (`app/kv_store.py`).
- **Monday.com** accessed read-only via GraphQL (`app/monday/`), with schema discovery and full cursor pagination — nothing is hardcoded from the CSVs.
- **Canonical model** (`app/canonical/`) maps raw Monday columns to a stable internal shape: alias matching first, then a type + value-shape fallback for boards where column titles don't match the expected names (see the Monday setup section below).
- **Normalization** (`app/normalize/`) — pure functions for dates, numbers, text, and statuses that never guess and never throw.
- **Validation** (`app/validate/`) — drops structurally corrupted rows (header-echo artifacts) before normalization, and builds a per-field data-quality report that treats 0%-filled fields as a structural absence rather than per-record noise.
- **BI engine** (`app/bi/`) — one deterministic function per metric family (pipeline, revenue, operations, sector performance, cross-board, leadership update). All arithmetic lives here; nothing here produces prose.
- **Agent** (`app/agent/`) — Gemini function-calling loop. Python renders the Answer/Key-metrics/Data-quality sections verbatim from typed tool results; Gemini's final turn writes only the Insight prose, enforced both by the system prompt and, since testing showed the model doesn't always follow that instruction, by code that strips anything duplicated.
- **Board summary** (`app/board_summary.py`) — reuses the same discovery/mapping/quality-report data to serve `GET /api/config/boards` (the frontend's setup screen) and to feed a short "connected boards this session" block into the system prompt for every turn.
- **Frontend** (`web/`) — a separate Next.js app: a setup page (`/`) previewing the two configured boards before chatting, and a chat page (`/chat`). Deployed independently of the backend; the plain `app/static/` HTML chat page still works standalone if you'd rather skip it.

## Monday.com setup

Import the two supplied CSVs as separate boards in your Monday.com workspace — one for **Deals**, one for **Work Orders**. Column *types* matter more than exact names: the agent maps columns by name first, and falls back to matching by column type plus the actual values in it when a title doesn't match anything it recognizes. So renamed or reordered columns generally still work, but using names close to these makes the mapping immediate and unambiguous:

### Deals board

| Column | Type | Notes |
| --- | --- | --- |
| Deal Name | Item name | |
| Owner code | Status/Dropdown | |
| Client Code | Status/Dropdown | |
| Deal Status | Status | Won / Dead / Open / On Hold |
| Close Date (A) | Date | Actual close date |
| Closure Probability | Status | High / Medium / Low |
| Deal Value | Numbers | |
| Tentative Close Date | Date | Expected close date |
| Deal Stage | Status | Pipeline stage |
| Product deal | Status | |
| Sector/service | Status/Dropdown | |
| Created Date | Date | |

### Work Orders board

| Column | Type | Notes |
| --- | --- | --- |
| Deal name masked | Item name / Text | |
| Customer Name Code | Status/Dropdown | |
| Execution Status | Status | |
| Sector | Status | |
| Amount Excl GST | Numbers | Contract value |
| Billed Value | Numbers | Incl. GST |
| Amount Receivable | Numbers | |
| Invoice Status | Status | |
| WO Status | Status | Open / Closed |
| AR Priority | Status/Checkbox | |
| Probable Start Date | Date | |
| Probable End Date | Date | |

Then set `MONDAY_API_TOKEN`, `DEALS_BOARD_ID`, `WORK_ORDERS_BOARD_ID` in your `.env` (board IDs are in the board's URL, or `Board menu → More actions → Developers`). The token needs read access to both boards; nothing here ever writes to Monday.

## Try it yourself

### Backend

```bash
python -m venv .venv
.venv/Scripts/activate        # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in your Monday token, board IDs, Gemini key
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for a bare-bones chat page, or run the fuller frontend below.

### Frontend (optional — a small Next.js app with the setup screen described above)

```bash
cd web
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. It needs the backend running and reachable.

### Tests

```bash
pytest tests/ -v
```

Covers the normalization edge cases, the row-corruption filter, field mapping against realistic messy columns, the board-summary/data-quality logic, and the actual BI math against hand-checked numbers.

## Running it in production

Deploys to Vercel as a serverless function (`api/index.py` → the FastAPI app). Two things a serverless setup breaks that this handles:

- **State.** Session history and the board cache used to live in plain memory, which doesn't survive between invocations on a serverless runtime. Both now go through Vercel KV / Upstash Redis when configured (`KV_REST_API_URL`, `KV_REST_API_TOKEN`) and fall back to memory locally, so you don't need Redis just to develop.
- **Time.** Fetching two boards and running the Gemini tool loop can bump up against the default 10-second function timeout. Both boards fetch in parallel now instead of one after another. `maxDuration` is set to 60s in `vercel.json`, which only actually applies on Vercel Pro — on the free tier it's clamped back down, so the parallel fetch is what actually keeps things fast, not the config value.

The frontend (`web/`) deploys separately — its own Vercel project, `FRONTEND_ORIGINS` set on the backend so CORS doesn't block it.

## Known limitations

- No real database. Restart the process (or hit a cold serverless start without Redis configured) and conversation history is gone.
- Deals and Work Orders can't be matched record-by-record — only sector-level comparison is honest given the data (see `DECISION_LOG.md`).
- Board data is cached for 2 minutes; it's never presented as more current than that.
- A few date fields on the Deals board couldn't be reliably identified on the live evaluation board and are left unmapped rather than guessed — see `DECISION_LOG.md`.
