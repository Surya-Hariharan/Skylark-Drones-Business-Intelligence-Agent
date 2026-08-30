from app.bi.pipeline import PipelineFilters, analyze_pipeline
from app.canonical.models import CanonicalDeal, ValueWithRaw


def _deal(id_, status="Open", stage="C", confidence=None, value=None, sector="Energy"):
    return CanonicalDeal(
        id=id_,
        name=f"Deal {id_}",
        status=status,
        stage=stage,
        close_confidence=confidence,
        value=ValueWithRaw(normalized=value, raw=str(value)) if value is not None else None,
        sector=sector,
    )


def test_only_open_and_on_hold_deals_count_as_pipeline():
    deals = [_deal("1", status="Open"), _deal("2", status="On Hold"), _deal("3", status="Won"), _deal("4", status="Dead")]
    result = analyze_pipeline(deals)
    assert result.total_open_deals == 2


def test_missing_value_excluded_from_total_but_counted():
    deals = [_deal("1", value=100), _deal("2", value=None), _deal("3", value=200)]
    result = analyze_pipeline(deals)
    assert result.total_open_value == 300
    assert result.excluded_count == 1
    assert any("no usable deal value" in c for c in result.caveats)


def test_all_values_missing_yields_none_not_zero():
    deals = [_deal("1", value=None), _deal("2", value=None)]
    result = analyze_pipeline(deals)
    assert result.total_open_value is None


def test_unclassified_confidence_tracked_separately_from_low():
    deals = [_deal("1", confidence="Low"), _deal("2", confidence=None), _deal("3", confidence=None)]
    result = analyze_pipeline(deals)
    assert result.by_close_confidence["Low"] == 1
    assert result.unclassified_confidence_count == 2


def test_sector_filter_scopes_results():
    deals = [_deal("1", sector="Energy"), _deal("2", sector="Healthcare")]
    result = analyze_pipeline(deals, PipelineFilters(sector="energy"))
    assert result.total_open_deals == 1
