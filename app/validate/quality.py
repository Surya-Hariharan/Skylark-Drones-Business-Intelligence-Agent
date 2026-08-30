from pydantic import BaseModel


class FieldQuality(BaseModel):
    field: str
    fetched: int
    used: int
    excluded: int
    missing: int
    fill_rate: float


class DataQualityReport(BaseModel):
    board: str
    total_fetched: int
    structurally_invalid_dropped: int
    total_used: int
    fields: list[FieldQuality]
    dropped_fields: list[str]


_NON_DATA_FIELDS = {"id", "raw_row", "name"}


def build_quality_report(
    board: str,
    total_fetched: int,
    structurally_invalid_dropped: int,
    canonical_records: list[BaseModel],
) -> DataQualityReport:
    """A field with 0% fill across the WHOLE dataset is a structural absence,
    not per-record noise: it's named once in `dropped_fields` instead of
    appearing in `fields` with fill_rate=0.0, so it isn't repeated as a
    caveat on every answer that would have touched it."""
    total_used = len(canonical_records)
    if total_used == 0:
        return DataQualityReport(
            board=board,
            total_fetched=total_fetched,
            structurally_invalid_dropped=structurally_invalid_dropped,
            total_used=0,
            fields=[],
            dropped_fields=[],
        )

    field_names = [
        name for name in type(canonical_records[0]).model_fields if name not in _NON_DATA_FIELDS
    ]

    fields: list[FieldQuality] = []
    dropped_fields: list[str] = []

    for field_name in field_names:
        filled = sum(1 for record in canonical_records if getattr(record, field_name) is not None)
        if filled == 0:
            dropped_fields.append(field_name)
            continue
        fields.append(
            FieldQuality(
                field=field_name,
                fetched=total_used,
                used=filled,
                excluded=total_used - filled,
                missing=total_used - filled,
                fill_rate=filled / total_used,
            )
        )

    return DataQualityReport(
        board=board,
        total_fetched=total_fetched,
        structurally_invalid_dropped=structurally_invalid_dropped,
        total_used=total_used,
        fields=fields,
        dropped_fields=dropped_fields,
    )
