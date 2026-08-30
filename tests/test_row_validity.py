from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef
from app.validate.row_validity import filter_structurally_valid, is_structurally_valid

SCHEMA = [
    ColumnDef(id="status_col", title="Deal Status", type="status"),
    ColumnDef(id="close_date_col", title="Close Date (A)", type="date"),
    ColumnDef(id="sector_col", title="Sector/service", type="text"),
]


def _item(item_id: str, status: str | None, close_date: str | None, sector: str | None) -> RawItem:
    return RawItem(
        id=item_id,
        name=f"Deal {item_id}",
        column_values={
            "status_col": {"text": status, "value": None},
            "close_date_col": {"text": close_date, "value": None},
            "sector_col": {"text": sector, "value": None},
        },
    )


def test_normal_row_is_valid():
    row = _item("1", "Won", "2026-01-01", "Energy")
    assert is_structurally_valid(row, SCHEMA) is True


def test_header_echo_row_is_invalid():
    # a column's raw value equals that column's own header text
    row = _item("2", "Deal Status", None, None)
    assert is_structurally_valid(row, SCHEMA) is False


def test_missing_values_are_not_treated_as_structurally_invalid():
    row = _item("3", None, None, None)
    assert is_structurally_valid(row, SCHEMA) is True


def test_filter_drops_only_junk_rows_and_counts_them():
    rows = [
        _item("1", "Won", "2026-01-01", "Energy"),
        _item("2", "Deal Status", None, None),
        _item("3", "Open", "2026-02-01", "Healthcare"),
        _item("4", None, None, "Sector/service"),  # header-echo on a different column
    ]
    valid, dropped = filter_structurally_valid(rows, SCHEMA)
    assert dropped == 2
    assert {r.id for r in valid} == {"1", "3"}
