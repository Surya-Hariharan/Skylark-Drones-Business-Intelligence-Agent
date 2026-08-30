from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef


def is_structurally_valid(row: RawItem, schema: list[ColumnDef]) -> bool:
    """False iff the row is a full echo of the header row: every filled
    non-name column's raw text equals that column's own header/title text,
    and at least one column is filled — the header-echo corruption case
    found in the real Deals sheet ("a stray Deal Name and everything else
    blank"). This is a structural-corruption check, distinct from
    missing/ambiguous data, and must run before normalization.

    Deliberately NOT "any single column matches its title": on a board
    whose column titles have been masked to literal option/value text (e.g.
    a status column literally titled "Renewables"), a normal row can
    legitimately hold that exact value in that one column. Requiring every
    filled column to match is what actually captures "this row is the
    header, repeated" rather than "this row happens to hold one value that
    coincides with a masked title"."""
    filled = 0
    matched = 0
    for column in schema:
        if column.type == "name":
            continue
        entry = row.column_values.get(column.id)
        if not entry:
            continue
        text = entry.get("text")
        if text is None or str(text).strip() == "":
            continue
        filled += 1
        if str(text).strip() == column.title.strip():
            matched += 1
    return not (matched > 0 and matched == filled)


def filter_structurally_valid(items: list[RawItem], schema: list[ColumnDef]) -> tuple[list[RawItem], int]:
    """Returns (valid_items, dropped_count)."""
    valid = [item for item in items if is_structurally_valid(item, schema)]
    return valid, len(items) - len(valid)
