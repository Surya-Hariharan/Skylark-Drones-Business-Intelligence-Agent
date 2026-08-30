from datetime import date

from pydantic import BaseModel

from app.canonical.models import CanonicalWorkOrder


class WorkOrderFilters(BaseModel):
    sector: str | None = None
    status: str | None = None
    time_from: date | None = None
    time_to: date | None = None


def apply_work_order_filters(
    work_orders: list[CanonicalWorkOrder], filters: WorkOrderFilters | None
) -> list[CanonicalWorkOrder]:
    if not filters:
        return work_orders
    result = work_orders
    if filters.sector:
        result = [w for w in result if w.sector and w.sector.lower() == filters.sector.lower()]
    if filters.status:
        result = [w for w in result if w.status and w.status.lower() == filters.status.lower()]
    if filters.time_from:
        result = [w for w in result if w.start_date and w.start_date >= filters.time_from]
    if filters.time_to:
        result = [w for w in result if w.start_date and w.start_date <= filters.time_to]
    return result
