from datetime import date

from pydantic import BaseModel

from app.canonical.models import CanonicalDeal

OPEN_STATUSES = {"Open", "On Hold"}
CLOSE_CONFIDENCE_LEVELS = ["High", "Medium", "Low"]


class PipelineFilters(BaseModel):
    sector: str | None = None
    stage: str | None = None
    time_from: date | None = None
    time_to: date | None = None


class PipelineResult(BaseModel):
    total_open_deals: int
    total_open_value: float | None
    by_stage: dict[str, int]
    by_close_confidence: dict[str, int]
    unclassified_confidence_count: int
    excluded_count: int
    caveats: list[str]


def _apply_filters(deals: list[CanonicalDeal], filters: PipelineFilters | None) -> list[CanonicalDeal]:
    if not filters:
        return deals
    result = deals
    if filters.sector:
        result = [d for d in result if d.sector and d.sector.lower() == filters.sector.lower()]
    if filters.stage:
        result = [d for d in result if d.stage and d.stage.lower() == filters.stage.lower()]
    if filters.time_from:
        result = [d for d in result if d.expected_close_date and d.expected_close_date >= filters.time_from]
    if filters.time_to:
        result = [d for d in result if d.expected_close_date and d.expected_close_date <= filters.time_to]
    return result


def analyze_pipeline(deals: list[CanonicalDeal], filters: PipelineFilters | None = None) -> PipelineResult:
    scoped = _apply_filters(deals, filters)
    open_deals = [d for d in scoped if d.status in OPEN_STATUSES]

    by_stage: dict[str, int] = {}
    for deal in open_deals:
        key = deal.stage or "Unknown stage"
        by_stage[key] = by_stage.get(key, 0) + 1

    by_close_confidence: dict[str, int] = {level: 0 for level in CLOSE_CONFIDENCE_LEVELS}
    unclassified = 0
    for deal in open_deals:
        if deal.close_confidence:
            by_close_confidence[deal.close_confidence] += 1
        else:
            unclassified += 1

    valued = [d.value.normalized for d in open_deals if d.value is not None]
    excluded_count = len(open_deals) - len(valued)
    total_open_value = sum(valued) if valued else None

    caveats = []
    if excluded_count:
        caveats.append(
            f"{excluded_count} of {len(open_deals)} open deals have no usable deal value and are excluded "
            "from the total open value figure."
        )
    if unclassified:
        caveats.append(
            f"{unclassified} open deals have no closure-probability classification at all "
            "(missing is not the same as 'Low')."
        )

    return PipelineResult(
        total_open_deals=len(open_deals),
        total_open_value=total_open_value,
        by_stage=by_stage,
        by_close_confidence=by_close_confidence,
        unclassified_confidence_count=unclassified,
        excluded_count=excluded_count,
        caveats=caveats,
    )
