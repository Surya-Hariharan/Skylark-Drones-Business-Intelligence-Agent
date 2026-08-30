from pydantic import BaseModel

from app.bi.common import WorkOrderFilters, apply_work_order_filters
from app.canonical.models import CanonicalWorkOrder


class OperationsResult(BaseModel):
    total_work_orders: int
    by_status: dict[str, int]
    by_billing_status: dict[str, int]
    ar_priority_count: int
    excluded_count: int
    caveats: list[str]


def analyze_operations(
    work_orders: list[CanonicalWorkOrder], filters: WorkOrderFilters | None = None
) -> OperationsResult:
    scoped = apply_work_order_filters(work_orders, filters)

    by_status: dict[str, int] = {}
    missing_status = 0
    for wo in scoped:
        if wo.status:
            by_status[wo.status] = by_status.get(wo.status, 0) + 1
        else:
            missing_status += 1

    by_billing_status: dict[str, int] = {}
    missing_billing = 0
    for wo in scoped:
        if wo.billing_status:
            by_billing_status[wo.billing_status] = by_billing_status.get(wo.billing_status, 0) + 1
        else:
            missing_billing += 1

    ar_priority_count = sum(1 for wo in scoped if wo.ar_priority)

    caveats = []
    if missing_status:
        caveats.append(f"{missing_status} of {len(scoped)} work orders have no execution status recorded.")
    if missing_billing:
        caveats.append(
            f"{missing_billing} of {len(scoped)} work orders have no billing status recorded — "
            "this field is sparsely filled in the source data."
        )

    return OperationsResult(
        total_work_orders=len(scoped),
        by_status=by_status,
        by_billing_status=by_billing_status,
        ar_priority_count=ar_priority_count,
        excluded_count=missing_status,
        caveats=caveats,
    )
