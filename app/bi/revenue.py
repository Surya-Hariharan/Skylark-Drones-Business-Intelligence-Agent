from enum import Enum

from pydantic import BaseModel

from app.bi.common import WorkOrderFilters, apply_work_order_filters
from app.canonical.models import CanonicalWorkOrder


class RevenueBasis(str, Enum):
    CONTRACT_EXCL_GST = "contract_value_excl_gst"
    BILLED_INCL_GST = "billed_value_incl_gst"
    RECEIVABLE = "receivable"


_BASIS_FIELD_AND_LABEL = {
    RevenueBasis.CONTRACT_EXCL_GST: ("contract_value", "Contract value (excl. GST)"),
    RevenueBasis.BILLED_INCL_GST: ("billed_value", "Billed value (incl. GST)"),
    RevenueBasis.RECEIVABLE: ("receivable", "Amount receivable"),
}


class RevenueResult(BaseModel):
    basis_used: RevenueBasis
    basis_label: str
    total: float
    by_sector: dict[str, float]
    excluded_count: int
    caveats: list[str]


def infer_revenue_basis(user_phrasing: str) -> RevenueBasis | None:
    """Best-effort inference from the user's own words (orchestrator calls
    this before invoking the tool). Returns None when phrasing gives no
    signal, letting analyze_revenue apply its conservative default."""
    text = user_phrasing.lower()
    if any(term in text for term in ("incl gst", "including gst", "invoice value", "billed to the client", "billed")):
        return RevenueBasis.BILLED_INCL_GST
    if any(term in text for term in ("receivable", "outstanding", "yet to collect", "yet to be collected")):
        return RevenueBasis.RECEIVABLE
    if any(term in text for term in ("contract value", "excl gst", "excluding gst")):
        return RevenueBasis.CONTRACT_EXCL_GST
    return None


def analyze_revenue(
    work_orders: list[CanonicalWorkOrder],
    filters: WorkOrderFilters | None = None,
    requested_basis: RevenueBasis | None = None,
) -> RevenueResult:
    """Never emits a bare 'revenue' number: always picks and labels one of
    {contract value, billed value, receivable}. If the caller (the
    orchestrator, from user phrasing) doesn't specify a basis, this defaults
    to the more conservative, tax-independent contract value excl. GST."""
    basis = requested_basis or RevenueBasis.CONTRACT_EXCL_GST
    field_name, label = _BASIS_FIELD_AND_LABEL[basis]

    scoped = apply_work_order_filters(work_orders, filters)
    valued: list[tuple[str, float]] = []
    for wo in scoped:
        amount = getattr(wo, field_name)
        if amount is not None:
            valued.append((wo.sector or "Unknown sector", amount.normalized))

    excluded_count = len(scoped) - len(valued)
    total = sum(v for _, v in valued)
    by_sector: dict[str, float] = {}
    for sector, amount in valued:
        by_sector[sector] = by_sector.get(sector, 0.0) + amount

    caveats = []
    if excluded_count:
        caveats.append(
            f"{excluded_count} of {len(scoped)} work orders have no usable {label.lower()} and are excluded "
            "from this total."
        )

    return RevenueResult(
        basis_used=basis,
        basis_label=label,
        total=total,
        by_sector=by_sector,
        excluded_count=excluded_count,
        caveats=caveats,
    )
