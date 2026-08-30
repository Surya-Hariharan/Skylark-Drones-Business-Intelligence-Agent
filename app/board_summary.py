from pydantic import BaseModel

from app.canonical.models import CanonicalDeal, CanonicalWorkOrder
from app.data_cache import BoardCacheEntry
from app.validate.quality import DataQualityReport

_LOW_FILL_THRESHOLD = 0.3
_HIGH_FILL_THRESHOLD = 0.95
_MAX_SAMPLE_SECTORS = 5


class BoardSummary(BaseModel):
    name: str
    connected: bool
    record_count: int
    kind: str = "unknown"
    fields: list[str] = []
    flags: list[str] = []
    failure_reason: str | None = None


def _flags_from_quality(quality: DataQualityReport | None) -> list[str]:
    if quality is None:
        return []
    flags: list[str] = []
    for field in quality.dropped_fields:
        flags.append(f"{field} missing on all records (excluded from the model)")
    for fr in quality.fields:
        if fr.fill_rate < _LOW_FILL_THRESHOLD:
            flags.append(f"{fr.field} missing on {round((1 - fr.fill_rate) * 100)}% of records")
        elif fr.field == "sector" and fr.fill_rate >= _HIGH_FILL_THRESHOLD:
            flags.append(f"Sector {round(fr.fill_rate * 100)}% filled — best cross-board comparison field")
    return flags


def _distinct_sectors(records: list[CanonicalDeal] | list[CanonicalWorkOrder]) -> list[str]:
    seen: list[str] = []
    for record in records:
        sector = getattr(record, "sector", None)
        if sector and sector not in seen:
            seen.append(sector)
    return seen


def build_board_summaries(board_data: BoardCacheEntry) -> list[BoardSummary]:
    """One entry per configured board, however many there are, reusing the
    discovery/classification/quality work `get_cached_board_data` already
    did — no separate BI logic here. Each board reports the kind that was
    inferred from its own schema, so the user can see when a board was read
    as something other than they expected, or not classified at all."""
    summaries: list[BoardSummary] = []

    for board in board_data.boards:
        if board.failure:
            summaries.append(
                BoardSummary(
                    name=board.board_name,
                    kind=board.kind.value,
                    connected=False,
                    record_count=0,
                    failure_reason=board.failure.reason,
                )
            )
            continue

        summaries.append(
            BoardSummary(
                name=board.board_name,
                kind=board.kind.value,
                connected=True,
                record_count=board.record_count,
                fields=[fr.field for fr in board.quality.fields] if board.quality else [],
                flags=_flags_from_quality(board.quality),
            )
        )

    return summaries


def render_session_context_block(board_data: BoardCacheEntry) -> str:
    """Live-discovery grounding appended to the system prompt for this
    session (system-prompt §9/§25): confidence/caveat language should
    reflect what was actually just fetched, not assumptions baked into the
    static system-prompt file. Regenerated from the same cached board data
    the tools use — not passed in from the client — so it can't go stale
    relative to the actual answer, or be spoofed.

    Also states which analyses are actually available given what connected.
    The tool layer already refuses a tool whose data is missing, but the
    model picks the tool before that refusal happens; telling it up front
    which capabilities exist is what stops it promising a cross-board
    comparison on a single connected board (§8)."""
    summaries = build_board_summaries(board_data)
    records_by_kind = {"deals": board_data.deals, "work_orders": board_data.work_orders}

    lines = [f"Connected boards this session: {len(summaries)} configured."]
    for summary in summaries:
        if not summary.connected:
            lines.append(f"- {summary.name}: NOT USABLE ({summary.failure_reason})")
            continue

        parts = [f"read as {summary.kind}", f"{summary.record_count} records"]
        sectors = _distinct_sectors(records_by_kind.get(summary.kind, []))
        if sectors:
            shown = "/".join(sectors[:_MAX_SAMPLE_SECTORS])
            if len(sectors) > _MAX_SAMPLE_SECTORS:
                shown += f" (+{len(sectors) - _MAX_SAMPLE_SECTORS} more)"
            parts.append(f"sectors: {shown}")
        parts.extend(summary.flags[:2])
        lines.append(f"- {summary.name}: " + ", ".join(parts))

    has_deals = bool(board_data.deals)
    has_work_orders = bool(board_data.work_orders)

    lines.append("")
    if has_deals and has_work_orders:
        lines.append(
            "Available analysis: all tools, including cross-board and leadership updates. "
            "Deals and Work Orders may only be joined on sector."
        )
    elif has_deals:
        lines.append(
            "Available analysis: pipeline and deal-side sector performance ONLY. No Work Orders "
            "board is connected, so revenue, operations, cross-board and leadership-update "
            "analysis are unavailable — say so plainly instead of estimating them."
        )
    elif has_work_orders:
        lines.append(
            "Available analysis: revenue and operations ONLY. No Deals board is connected, so "
            "pipeline, cross-board and leadership-update analysis are unavailable — say so "
            "plainly instead of estimating them."
        )
    else:
        lines.append(
            "NO usable business data is connected. Do not answer any business question with "
            "numbers; explain that no board could be read and what the failure was."
        )

    return "\n".join(lines)
