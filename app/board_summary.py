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
    """One entry per configured board (system-prompt §1: the assignment
    fixes the shape to exactly Deals + Work Orders, not an arbitrary list),
    reusing the discovery/canonical-mapping/quality-report work
    `get_cached_board_data` already did — no separate BI logic here."""
    summaries: list[BoardSummary] = []

    if board_data.deal_failure:
        summaries.append(
            BoardSummary(
                name="Deals", connected=False, record_count=0, failure_reason=board_data.deal_failure.reason
            )
        )
    else:
        fields = [fr.field for fr in board_data.deal_quality.fields] if board_data.deal_quality else []
        summaries.append(
            BoardSummary(
                name="Deals",
                connected=True,
                record_count=len(board_data.deals),
                fields=fields,
                flags=_flags_from_quality(board_data.deal_quality),
            )
        )

    if board_data.wo_failure:
        summaries.append(
            BoardSummary(
                name="Work Orders", connected=False, record_count=0, failure_reason=board_data.wo_failure.reason
            )
        )
    else:
        fields = [fr.field for fr in board_data.wo_quality.fields] if board_data.wo_quality else []
        summaries.append(
            BoardSummary(
                name="Work Orders",
                connected=True,
                record_count=len(board_data.work_orders),
                fields=fields,
                flags=_flags_from_quality(board_data.wo_quality),
            )
        )

    return summaries


def render_session_context_block(board_data: BoardCacheEntry) -> str:
    """Live-discovery grounding appended to the system prompt for this
    session (system-prompt §9/§25): confidence/caveat language should
    reflect what was actually just fetched, not assumptions baked into the
    static system-prompt file. Regenerated from the same cached board data
    the tools use — not passed in from the frontend — so it can't go stale
    relative to the actual answer, or be spoofed by the client."""
    summaries = build_board_summaries(board_data)
    records_by_board = {"Deals": board_data.deals, "Work Orders": board_data.work_orders}

    lines = ["Connected boards this session:"]
    for summary in summaries:
        if not summary.connected:
            lines.append(f"- {summary.name}: NOT CONNECTED ({summary.failure_reason})")
            continue

        parts = [f"{summary.record_count} records"]
        sectors = _distinct_sectors(records_by_board[summary.name])
        if sectors:
            shown = "/".join(sectors[:_MAX_SAMPLE_SECTORS])
            if len(sectors) > _MAX_SAMPLE_SECTORS:
                shown += f" (+{len(sectors) - _MAX_SAMPLE_SECTORS} more)"
            parts.append(f"sectors: {shown}")
        parts.extend(summary.flags[:2])
        lines.append(f"- {summary.name}: " + ", ".join(parts))

    return "\n".join(lines)
