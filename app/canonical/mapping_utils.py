import re

from pydantic import BaseModel

from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef


class FieldSpec(BaseModel):
    field: str
    aliases: list[str]
    # Fallback matching (only used if no alias title matches): restrict to
    # these Monday column types, and optionally require sample-value overlap
    # against a known domain (`expected_values`) or a majority regex match
    # (`value_pattern`) before binding. Kept narrow deliberately — a wrong
    # guess on a free-text field is worse than surfacing "unmapped". Checked
    # in that order; only one of the two is used per spec.
    monday_types: list[str] = []
    expected_values: set[str] | None = None
    value_pattern: str | None = None


def resolve_column_mapping(
    schema: list[ColumnDef], items: list[RawItem], specs: list[FieldSpec]
) -> dict[str, str]:
    """Column-name-driven mapping with a type+sample-value fallback for a
    re-labeled board. Returns canonical field name -> Monday column id."""
    title_to_col = {c.title.strip().lower(): c for c in schema}
    mapping: dict[str, str] = {}
    claimed: set[str] = set()

    for spec in specs:
        for alias in spec.aliases:
            col = title_to_col.get(alias.strip().lower())
            if col:
                mapping[spec.field] = col.id
                claimed.add(col.id)
                break

    for spec in specs:
        if spec.field in mapping or not spec.monday_types:
            continue
        candidates = [c for c in schema if c.id not in claimed and c.type in spec.monday_types]
        if not candidates:
            continue

        if spec.expected_values and items:
            best_col, best_overlap = None, 0
            for col in candidates:
                samples = {
                    (item.column_values.get(col.id) or {}).get("text") or "" for item in items[:30]
                }
                samples = {s.strip() for s in samples if s.strip()}
                overlap = len(samples & spec.expected_values)
                if overlap > best_overlap:
                    best_col, best_overlap = col, overlap
            if best_col:
                mapping[spec.field] = best_col.id
                claimed.add(best_col.id)
        elif spec.value_pattern and items:
            # A column whose title itself has been masked (replaced with one
            # of its own sample values) can't be matched by alias or by a
            # fixed value domain, but its values still follow a recognizable
            # shape (e.g. "OWNER_003", "A. Lead Generated"). Bind to whichever
            # unclaimed candidate has the highest share of sampled values
            # matching that shape, provided a clear majority does.
            pattern = re.compile(spec.value_pattern)
            best_col, best_ratio = None, 0.0
            for col in candidates:
                samples = [
                    ((item.column_values.get(col.id) or {}).get("text") or "").strip()
                    for item in items[:50]
                ]
                samples = [s for s in samples if s]
                if not samples:
                    continue
                ratio = sum(1 for s in samples if pattern.fullmatch(s)) / len(samples)
                if ratio > best_ratio:
                    best_col, best_ratio = col, ratio
            if best_col and best_ratio >= 0.6:
                mapping[spec.field] = best_col.id
                claimed.add(best_col.id)
        elif len(candidates) == 1:
            mapping[spec.field] = candidates[0].id
            claimed.add(candidates[0].id)

    return mapping


def get_text(item: RawItem, column_mapping: dict[str, str], field: str) -> str | None:
    col_id = column_mapping.get(field)
    if col_id is None:
        return None
    entry = item.column_values.get(col_id)
    if not entry:
        return None
    return entry.get("text")
