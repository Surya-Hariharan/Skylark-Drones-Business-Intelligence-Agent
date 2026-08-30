from app.canonical.mapping_utils import FieldSpec, get_text, resolve_column_mapping
from app.canonical.models import CanonicalWorkOrder, ValueWithRaw
from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef
from app.normalize.dates import normalize_date
from app.normalize.numbers import normalize_number
from app.normalize.status import normalize_status
from app.normalize.text import normalize_text

BILLING_STATUS_DOMAIN = ["Open", "Closed"]

# Fields that are 0% filled in the assignment's dev data (Collection status,
# Expected Billing Month, Actual Collection Month) are deliberately absent
# from the canonical model — they're a structural absence, not per-record
# noise, per the data-quality rules. If the eval-environment board has these
# filled in, they'd need to be added back to the model and specs.

WORK_ORDER_FIELD_SPECS = [
    FieldSpec(field="deal_name", aliases=["Deal name masked", "Deal Name"]),
    FieldSpec(field="client_id", aliases=["Customer Name Code", "Client Code"]),
    FieldSpec(field="status", aliases=["Execution Status", "Status"]),
    FieldSpec(field="sector", aliases=["Sector"]),
    FieldSpec(
        field="contract_value",
        aliases=["Amount in Rupees (Excl of GST) (Masked)", "Amount Excl GST"],
        monday_types=["numbers"],
    ),
    FieldSpec(
        field="billed_value",
        aliases=[
            "Billed Value (Incl GST) (Masked)",
            "Billed Value",
            "Billed Value in Rupees (Incl of GST.) (Masked)",
        ],
        monday_types=["numbers"],
    ),
    FieldSpec(field="receivable", aliases=["Amount Receivable (Masked)", "Amount Receivable"], monday_types=["numbers"]),
    FieldSpec(field="invoice_status", aliases=["Invoice Status"]),
    FieldSpec(
        field="billing_status",
        aliases=["WO Status (billed)", "WO Status"],
        monday_types=["status", "dropdown", "color"],
        expected_values=set(BILLING_STATUS_DOMAIN),
    ),
    FieldSpec(field="ar_priority", aliases=["AR Priority account", "AR Priority"]),
    FieldSpec(field="start_date", aliases=["Probable Start Date"], monday_types=["date"]),
    FieldSpec(field="end_date", aliases=["Probable End Date"], monday_types=["date"]),
]


def build_work_order_column_mapping(schema: list[ColumnDef], items: list[RawItem]) -> dict[str, str]:
    return resolve_column_mapping(schema, items, WORK_ORDER_FIELD_SPECS)


def _normalize_value_field(raw: str | None) -> ValueWithRaw | None:
    result = normalize_number(raw)
    if result.value is None:
        return None
    return ValueWithRaw(normalized=result.value, unit=result.unit, raw=result.raw)


def _normalize_ar_priority(raw: str | None) -> bool | None:
    if raw is None or not str(raw).strip():
        return None
    lowered = str(raw).strip().lower()
    if lowered in ("true", "yes", "y", "1", "checked", "priority"):
        return True
    if lowered in ("false", "no", "n", "0", "unchecked"):
        return False
    return None


def map_work_order_row(item: RawItem, column_mapping: dict[str, str]) -> CanonicalWorkOrder:
    return CanonicalWorkOrder(
        id=item.id,
        deal_name=normalize_text(get_text(item, column_mapping, "deal_name")).value,
        client_id=normalize_text(get_text(item, column_mapping, "client_id")).value,
        status=normalize_text(get_text(item, column_mapping, "status")).value,
        sector=normalize_text(get_text(item, column_mapping, "sector")).value,
        contract_value=_normalize_value_field(get_text(item, column_mapping, "contract_value")),
        billed_value=_normalize_value_field(get_text(item, column_mapping, "billed_value")),
        receivable=_normalize_value_field(get_text(item, column_mapping, "receivable")),
        invoice_status=normalize_text(get_text(item, column_mapping, "invoice_status")).value,
        billing_status=normalize_status(get_text(item, column_mapping, "billing_status"), BILLING_STATUS_DOMAIN).value,
        ar_priority=_normalize_ar_priority(get_text(item, column_mapping, "ar_priority")),
        start_date=normalize_date(get_text(item, column_mapping, "start_date")).date,
        end_date=normalize_date(get_text(item, column_mapping, "end_date")).date,
        raw_row=item.column_values,
    )


def map_work_orders(items: list[RawItem], schema: list[ColumnDef]) -> list[CanonicalWorkOrder]:
    column_mapping = build_work_order_column_mapping(schema, items)
    return [map_work_order_row(item, column_mapping) for item in items]
