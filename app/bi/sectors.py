from pydantic import BaseModel

from app.bi.pipeline import OPEN_STATUSES
from app.bi.revenue import RevenueBasis, analyze_revenue
from app.bi.common import WorkOrderFilters
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder


class SectorResult(BaseModel):
    sector: str | None
    deal_count: int
    open_pipeline_value: float | None
    work_order_count: int
    revenue_total: float | None
    revenue_basis_label: str | None
    caveats: list[str]


def analyze_sector_performance(
    deals: list[CanonicalDeal],
    work_orders: list[CanonicalWorkOrder],
    sector: str | None = None,
) -> SectorResult:
    """If `sector` is given, scopes to that sector only; if None, aggregates
    across all sectors (an overall summary)."""
    if sector:
        deal_scope = [d for d in deals if d.sector and d.sector.lower() == sector.lower()]
        wo_scope = [w for w in work_orders if w.sector and w.sector.lower() == sector.lower()]
    else:
        deal_scope = deals
        wo_scope = work_orders

    open_deals = [d for d in deal_scope if d.status in OPEN_STATUSES]
    valued = [d.value.normalized for d in open_deals if d.value is not None]
    open_pipeline_value = sum(valued) if valued else None

    revenue = analyze_revenue(wo_scope, filters=None, requested_basis=RevenueBasis.CONTRACT_EXCL_GST)

    caveats = []
    if open_deals and len(valued) < len(open_deals):
        caveats.append(
            f"{len(open_deals) - len(valued)} of {len(open_deals)} open deals in this scope have no usable value."
        )
    caveats.extend(revenue.caveats)

    return SectorResult(
        sector=sector,
        deal_count=len(deal_scope),
        open_pipeline_value=open_pipeline_value,
        work_order_count=len(wo_scope),
        revenue_total=revenue.total if wo_scope else None,
        revenue_basis_label=revenue.basis_label if wo_scope else None,
        caveats=caveats,
    )
