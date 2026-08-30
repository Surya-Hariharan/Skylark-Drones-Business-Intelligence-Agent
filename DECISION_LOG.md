# Decision Log

## Key assumptions

- The two boards are fixed — Deals (sales pipeline) and Work Orders (project execution). No support for arbitrary board configurations; the assignment fixes this shape, so a generic "connect any board" wizard would be solving a problem that doesn't exist here.
- "Revenue" is ambiguous in the raw data — contract value, billed value, and receivable each carry different GST treatment and mean different things. When a user's phrasing gives no signal, the agent defaults to contract value excl. GST (the more conservative figure) and always labels which basis it used, rather than emitting a bare "revenue" number.
- Deals and Work Orders can't be joined at the individual-record level. Deal names repeat and aren't unique (e.g. "Sakura" appears three times), and the client-code schemes are entirely different across boards (`COMPANYNNN` vs `WOCOMPANY_0xx`, zero overlap). Sector is the one clean, high-fill field both boards share, so cross-board comparisons are sector-level only, and every such answer says so explicitly.
- Closure-probability is categorical (High/Medium/Low) with no documented numeric mapping anywhere in the source data. Reported as-is; no invented win-percentage.
- A row that's a literal copy of its own header row (a sheet-merge artifact — two rows in the dev data have this) is a structural corruption, not a data-quality issue, and gets dropped before normalization rather than treated as an unusual-but-valid record.

## Trade-offs chosen and why

**The LLM never does arithmetic.** Every BI question (pipeline, revenue, operations, sector performance, cross-board, leadership update) runs through a deterministic Python function with its own tests; Gemini's only job is to explain the result in one short paragraph. This costs an extra layer of typed contracts and rendering code instead of just handing the model data and a prompt — but it means a number shown to a founder is never at risk of being quietly wrong or re-derived differently between two similar questions.

That boundary started as an instruction in the system prompt alone. Testing against the live evaluation boards showed Gemini doesn't reliably follow it — on some turns it re-generated its own copy of the Answer/Metrics/Data-quality sections inside its explanation, duplicating numbers already rendered correctly by code. I backed the boundary with actual code (strips anything that looks like duplicated structure before it reaches the user) rather than trusting the prompt instruction alone.

**Column mapping uses alias matching first, then a type + value-shape fallback.** This exists because the live evaluation board's column titles turned out to be masked to one of their own sample values — a status column literally titled `"Renewables"` instead of `"Sector"`. Without a fallback that recognizes fields by the *shape* of their values (an owner code looks like `OWNER_003`, a pipeline stage looks like `A. Lead Generated`) rather than only the column title, several fields — including sector, which cross-board comparison depends on entirely — would have silently gone unmapped. Testing against the real boards also caught the header-echo detector itself producing false positives for the same masking reason (57% of Deals rows were being wrongly dropped); fixed to require the whole row to be an echo, not one coincidental value match.

**Hosted on Vercel as a serverless function, not a persistent process.** Free, fast to stand up, and satisfies "testable via a link" with no server to babysit. The real cost: no in-memory state survives between invocations, so session history and the board-data cache had to move to Vercel KV / Upstash Redis rather than a plain in-process dict. Falls back to memory automatically for local development, so Redis isn't required just to run it locally.

**The frontend is a small separate Next.js app**, not more hand-rolled static HTML. This means two deployables instead of one, but it gets a real setup/preview screen — board connection status, record counts, mapped fields, data-quality flags — built from the exact same live discovery the chat agent uses, before the user starts asking questions.

## What I'd do differently with more time

- The three date fields on the Deals board (expected close, actual close, created date) are three identically-typed columns with no distinguishing signal on the masked live board — left unmapped rather than guess wrong. With more time I'd look for weaker secondary signals (date-range plausibility against deal status, for instance) before giving up on them entirely.
- On cross-board comparison questions specifically, Gemini sometimes skips free-form explanation and jumps straight to its own structured breakdown, which the code then reduces to a generic placeholder rather than a real qualitative read of the numbers. Safe, but weaker than it should be — worth another system-prompt pass.
- When one turn genuinely needs two tool calls (e.g. "billed this year vs. receivables?"), only the *last* call's result renders into the structured Answer/Key metrics — the model's own explanation referenced both numbers, but the figures the user actually sees only reflected one. I'd merge same-turn tool results into one response with more time.
- The model duplicates the Answer/Metrics/Data-quality structure inside its explanation using either markdown headers or plain "Label:" lines; the code now strips both, but a narrower response schema on the model's final turn would be a cleaner fix than post-hoc stripping.
- The Gemini free tier caps at 20 requests/day per model — fine for spot-checking, not for a real evaluation session. Worth a paid tier before the hosted prototype gets tested at length.
- Sessions are a UUID in the browser's `localStorage` with a 1-hour Redis TTL and no authentication — fine for a prototype a founder tries out, not for a real multi-user deployment.
- I'd build a small fixture from the actual live boards (not just the original dev CSVs) so future changes get checked against the messier real shape automatically, instead of relying on the kind of manual spot-check that caught the two live-data bugs above.

## How I interpreted "leadership updates"

I read this as: give a founder something they could paste directly into a leadership deck or Slack update, not a raw data export they'd still have to summarize themselves. `generate_leadership_update` runs the pipeline, operations, and revenue analyses together and returns one fixed structure — pipeline totals, operational status, financial figures, top sectors, and whatever caveats materially matter — with Gemini writing only an Executive Summary and a Key Takeaway on top of those numbers, never regenerating or restating them itself. It's implemented as one tool composing the outputs of the others rather than a separate reporting pipeline, since the underlying numbers are identical to what pipeline/revenue/operations already compute individually.
