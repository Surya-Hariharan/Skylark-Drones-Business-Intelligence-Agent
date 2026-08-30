from app.canonical.models import CanonicalWorkOrder
from app.validate.quality import build_quality_report


def test_zero_percent_filled_field_is_dropped_not_reported_as_zero():
    records = [
        CanonicalWorkOrder(id="1", sector="Energy"),
        CanonicalWorkOrder(id="2", sector="Healthcare"),
    ]
    report = build_quality_report("Work Orders", total_fetched=2, structurally_invalid_dropped=0, canonical_records=records)
    field_names = {f.field for f in report.fields}
    assert "sector" in field_names
    assert "invoice_status" not in field_names
    assert "invoice_status" in report.dropped_fields


def test_partially_filled_field_reports_fill_rate():
    records = [
        CanonicalWorkOrder(id="1", sector="Energy", invoice_status="Billed"),
        CanonicalWorkOrder(id="2", sector="Healthcare", invoice_status=None),
    ]
    report = build_quality_report("Work Orders", total_fetched=2, structurally_invalid_dropped=0, canonical_records=records)
    field = next(f for f in report.fields if f.field == "invoice_status")
    assert field.fill_rate == 0.5
    assert field.missing == 1
