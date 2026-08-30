from app.canonical.mapping_utils import FieldSpec, get_text, resolve_column_mapping
from app.canonical.models import CanonicalDeal, ValueWithRaw
from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef
from app.normalize.dates import normalize_date
from app.normalize.numbers import normalize_number
from app.normalize.status import normalize_status
from app.normalize.text import normalize_text

DEAL_STATUS_DOMAIN = ["Won", "Dead", "Open", "On Hold"]
CLOSE_CONFIDENCE_DOMAIN = ["High", "Medium", "Low"]
# Business-vocabulary sector labels observed across both boards (Deals and
# Work Orders share the same sector taxonomy — see DECISION_LOG.md). Used
# only as a fallback overlap check, same category of judgment call as the
# two domains above — never invented, just a fixed set this business uses.
SECTOR_DOMAIN = [
    "Mining", "Renewables", "Railways", "Powerline", "Others",
    "Construction", "DSP", "Tender", "Roads", "Agriculture",
]

DEAL_FIELD_SPECS = [
    FieldSpec(field="name", aliases=["Deal Name"]),
    # No fixed value domain exists for owner/client codes, but on a board
    # whose column titles have been masked (replaced with one of the
    # column's own sample values, e.g. a title of literally "OWNER_003"),
    # the values still follow a recognizable "OWNER_NNN" / "COMPANYNNN"
    # shape — see the value_pattern fallback in resolve_column_mapping.
    FieldSpec(
        field="owner_id",
        aliases=["Owner code", "Owner Code"],
        monday_types=["status", "dropdown"],
        value_pattern=r"OWNER_\d+",
    ),
    FieldSpec(
        field="client_id",
        aliases=["Client Code"],
        monday_types=["status", "dropdown"],
        value_pattern=r"COMPANY\d+",
    ),
    FieldSpec(
        field="status",
        aliases=["Deal Status", "Status"],
        monday_types=["status", "dropdown", "color"],
        expected_values=set(DEAL_STATUS_DOMAIN),
    ),
    FieldSpec(field="actual_close_date", aliases=["Close Date (A)", "Close Date"], monday_types=["date"]),
    FieldSpec(
        field="close_confidence",
        aliases=["Closure Probability", "Close Probability"],
        monday_types=["status", "dropdown", "color"],
        expected_values=set(CLOSE_CONFIDENCE_DOMAIN),
    ),
    FieldSpec(field="value", aliases=["Masked Deal value", "Deal Value", "Opportunity Amount"], monday_types=["numbers"]),
    FieldSpec(field="expected_close_date", aliases=["Tentative Close Date"], monday_types=["date"]),
    # Pipeline-stage labels observed on the real board follow a consistent
    # "<letter>. <description>" convention (e.g. "A. Lead Generated",
    # "G. Project Won") distinct from any other status-type column.
    FieldSpec(
        field="stage",
        aliases=["Deal Stage"],
        monday_types=["status", "dropdown"],
        value_pattern=r"[A-Za-z]\..+",
    ),
    FieldSpec(field="product_type", aliases=["Product deal", "Product Deal"]),
    FieldSpec(
        field="sector",
        aliases=["Sector/service", "Sector", "Sector/Service"],
        monday_types=["status", "dropdown", "color"],
        expected_values=set(SECTOR_DOMAIN),
    ),
    FieldSpec(field="created_date", aliases=["Created Date"], monday_types=["date", "creation_log"]),
]


def build_deal_column_mapping(schema: list[ColumnDef], items: list[RawItem]) -> dict[str, str]:
    return resolve_column_mapping(schema, items, DEAL_FIELD_SPECS)


def map_deal_row(item: RawItem, column_mapping: dict[str, str]) -> CanonicalDeal:
    name = get_text(item, column_mapping, "name") or item.name

    value_raw = get_text(item, column_mapping, "value")
    value_result = normalize_number(value_raw)
    value = (
        ValueWithRaw(normalized=value_result.value, unit=value_result.unit, raw=value_result.raw)
        if value_result.value is not None
        else None
    )

    return CanonicalDeal(
        id=item.id,
        name=name,
        owner_id=normalize_text(get_text(item, column_mapping, "owner_id")).value,
        client_id=normalize_text(get_text(item, column_mapping, "client_id")).value,
        status=normalize_status(get_text(item, column_mapping, "status"), DEAL_STATUS_DOMAIN).value,
        stage=normalize_text(get_text(item, column_mapping, "stage")).value,
        value=value,
        close_confidence=normalize_status(
            get_text(item, column_mapping, "close_confidence"), CLOSE_CONFIDENCE_DOMAIN
        ).value,
        expected_close_date=normalize_date(get_text(item, column_mapping, "expected_close_date")).date,
        actual_close_date=normalize_date(get_text(item, column_mapping, "actual_close_date")).date,
        created_date=normalize_date(get_text(item, column_mapping, "created_date")).date,
        sector=normalize_text(get_text(item, column_mapping, "sector")).value,
        product_type=normalize_text(get_text(item, column_mapping, "product_type")).value,
        raw_row=item.column_values,
    )


def map_deals(items: list[RawItem], schema: list[ColumnDef]) -> list[CanonicalDeal]:
    column_mapping = build_deal_column_mapping(schema, items)
    return [map_deal_row(item, column_mapping) for item in items]
