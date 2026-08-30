# Skylark BI Agent

Skylark Drones runs its business on Monday.com boards — Deals and Work Orders. Anyone who wants to know "how's our pipeline looking" or "which sectors are we actually delivering on" has to open Monday, filter, scroll, and do the math by hand. This is a chat agent that does that instead — you ask a plain-English question, it pulls the live boards, computes the real numbers, and answers like a person would.

The one rule I held myself to: **the LLM never does arithmetic.** Every number you see was computed in Python from the actual board data. Gemini's only job is to read those numbers and explain what they mean in plain business language.

For the reasoning behind the non-obvious calls (why sector-only cross-board comparison, why this deploy target, what I'd change with more time, how I read "leadership updates") see `DECISION_LOG.md`. This file covers architecture and how to run it.

## How it works, end to end

1. You ask something like *"what's our open pipeline in Renewables?"*
2. The agent figures out which of six BI tools answers that (pipeline, revenue, operations, sector performance, cross-board, or leadership update) and what filters apply.
3. That tool runs against data already fetched and cleaned from Monday: schema discovered dynamically, junk rows dropped, values normalized, everything mapped into a stable internal shape.
4. The tool returns exact numbers plus whatever caveats matter ("12 of 41 deals have no value on file"). Python renders the Answer, Key Metrics, and Data Quality sections straight from that — no LLM involved.
5. Gemini writes one short paragraph explaining what the numbers mean for the business. That's it — it doesn't get to touch the figures.

## Architecture

- **Streamlit** front end (`streamlit_app.py`) calling the agent in-process — no HTTP layer, no CORS, no separate server. Conversation state and the fetched-board cache live in process memory, which is correct for a single long-lived process.
- **Monday.com** accessed read-only via GraphQL (`app/monday/`), with schema discovery and full cursor pagination — nothing is hardcoded from the CSVs.
- **Canonical model** (`app/canonical/`) maps raw Monday columns to a stable internal shape: alias matching first, then a type + value-shape fallback for boards where column titles don't match the expected names (see the Monday setup section below).
- **Normalization** (`app/normalize/`) — pure functions for dates, numbers, text, and statuses that never guess and never throw.
- **Validation** (`app/validate/`) — drops structurally corrupted rows (header-echo artifacts) before normalization, and builds a per-field data-quality report that treats 0%-filled fields as a structural absence rather than per-record noise.
- **BI engine** (`app/bi/`) — one deterministic function per metric family (pipeline, revenue, operations, sector performance, cross-board, leadership update). All arithmetic lives here; nothing here produces prose.
- **Agent** (`app/agent/`) — Gemini function-calling loop. Python renders the Answer/Key-metrics/Data-quality sections verbatim from typed tool results; Gemini's final turn writes only the Insight prose, enforced both by the system prompt and, since testing showed the model doesn't always follow that instruction, by code that strips anything duplicated.
- **Board classification** (`app/canonical/board_kind.py`) — infers what each connected board *is* from its own discovered schema, by scoring how much of each mapper's field spec resolves against it. A board matching neither model closely enough stays `unknown` and is excluded from analysis rather than being forced into the closer of the two, since a misclassified board would silently corrupt every downstream number.
- **Board summary** (`app/board_summary.py`) — reuses the same discovery/classification/quality data to render the sidebar and to feed a "connected boards this session" block into the system prompt each turn, including which analyses are actually possible given what loaded.

### Any number of boards

The agent takes a comma-separated `MONDAY_BOARD_IDS` and adapts to whatever is behind it — the list's *order carries no meaning*, because each board's kind comes from its own schema. What's connected changes what the agent will do:

| Connected | Behaviour |
| --- | --- |
| A Deals board **and** a Work Orders board | All six tools, including cross-board and leadership updates |
| Deals only | Pipeline and deal-side sector performance; revenue/operations/cross-board refused, not estimated |
| Work Orders only | Revenue and operations; pipeline/cross-board refused |
| Several boards of one kind | Records pool into one deal set / work-order set (e.g. one board per region) |
| A board matching neither model | Reported as connected-but-unusable, excluded from every metric |
| Nothing usable | Refuses to answer business questions with numbers at all |

Gating happens in two places: the system-prompt context block tells the model up front which analyses exist (so it doesn't *offer* a cross-board comparison it can't run), and the tool layer independently refuses a tool whose data is missing.

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

Then set `MONDAY_API_TOKEN` and `MONDAY_BOARD_IDS` (comma-separated) in your `.env` — board IDs are in the board's URL, or `Board menu → More actions → Developers`. List them in any order; each board is identified by its own schema. The token needs read access to every board listed; nothing here ever writes to Monday.

## Try it yourself

```bash
python -m venv .venv
.venv/Scripts/activate        # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in your Monday token, board IDs, Gemini key
streamlit run streamlit_app.py
```

Open http://localhost:8501. The sidebar shows each connected board, the kind it was read as, its data-quality flags, and which analyses are available.

### Tests

```bash
pytest tests/ -v
```

Covers the normalization edge cases, the row-corruption filter, field mapping against realistic messy columns, board classification (including that an unrelated board is left `unknown` rather than forced), capability gating when only one kind of board is connected, confidence scoring, and the actual BI math against hand-checked numbers.

## Known limitations

- No real database. Restart the process and conversation history is gone.
- Deals and Work Orders can't be matched record-by-record — only sector-level comparison is honest given the data (see `DECISION_LOG.md`).
- Board data is cached for 2 minutes; it's never presented as more current than that.
- A few date fields on the Deals board couldn't be reliably identified on the live evaluation board and are left unmapped rather than guessed — see `DECISION_LOG.md`.
