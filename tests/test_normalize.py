from app.normalize.dates import normalize_date
from app.normalize.numbers import normalize_number
from app.normalize.status import normalize_status
from app.normalize.text import normalize_text


def test_normalize_number_extracts_value_and_unit():
    result = normalize_number("5,360 HA")
    assert result.value == 5360.0
    assert result.unit == "HA"
    assert result.raw == "5,360 HA"


def test_normalize_number_handles_currency_symbol():
    result = normalize_number("₹1,200,000")
    assert result.value == 1_200_000.0


def test_normalize_number_missing_is_none_not_zero():
    result = normalize_number(None)
    assert result.value is None
    result = normalize_number("")
    assert result.value is None


def test_normalize_number_unparseable_stays_none():
    result = normalize_number("not a number")
    assert result.value is None
    assert result.raw == "not a number"


def test_normalize_date_iso_parses_cleanly():
    result = normalize_date("2026-03-05")
    assert result.date is not None
    assert result.ambiguous is False


def test_normalize_date_ambiguous_slash_format_flagged():
    result = normalize_date("01/02/2026")
    assert result.date is None
    assert result.ambiguous is True


def test_normalize_date_unambiguous_slash_format_parses():
    result = normalize_date("25/12/2026")
    assert result.date is not None
    assert result.ambiguous is False
    assert result.date.day == 25
    assert result.date.month == 12


def test_normalize_date_missing_is_none():
    result = normalize_date(None)
    assert result.date is None
    assert result.ambiguous is False


def test_normalize_status_matches_domain_case_insensitively():
    result = normalize_status("won", ["Won", "Dead", "Open", "On Hold"])
    assert result.value == "Won"


def test_normalize_status_unmatched_preserves_raw_but_no_value():
    result = normalize_status("Weird Status", ["Won", "Dead", "Open", "On Hold"])
    assert result.value is None
    assert result.raw == "Weird Status"


def test_normalize_text_trims_whitespace():
    result = normalize_text("  Energy Sector  ")
    assert result.value == "Energy Sector"


def test_normalize_text_alias_table_maps_known_variant():
    result = normalize_text("ENERGY", alias_table={"energy": "Energy"})
    assert result.value == "Energy"
