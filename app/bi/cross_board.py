from typing import Literal

from pydantic import BaseModel

from app.bi.sectors import SectorResult, analyze_sector_performance
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder

JOIN_CAVEAT = (
    "Compared at sector level; individual deals could not be reliably matched to "
    "work orders across boards."
)


class CrossBoardResult(BaseModel):
    join_key: Literal["sector"] = "sector"
    join_caveat: str = JOIN_CAVEAT
    by_sector: list[SectorResult]


def analyze_cross_board(deals: list[CanonicalDeal], work_orders: list[CanonicalWorkOrder]) -> CrossBoardResult:
    """Joins Deals and Work Orders ONLY on sector — never on deal name or
    client code. Those fields use incompatible ID schemes across the two
    boards (see DECISION_LOG.md) and any name/code-based join would fabricate
    a relationship the data doesn't support (system-prompt §18/§19)."""
    sectors = sorted(
        {d.sector for d in deals if d.sector} | {w.sector for w in work_orders if w.sector}
    )
    by_sector = [analyze_sector_performance(deals, work_orders, sector=sector) for sector in sectors]
    return CrossBoardResult(by_sector=by_sector)
