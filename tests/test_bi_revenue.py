from app.bi.revenue import RevenueBasis, analyze_revenue, infer_revenue_basis
from app.canonical.models import CanonicalWorkOrder, ValueWithRaw


def _wo(id_, contract=None, billed=None, receivable=None, sector="Energy"):
    return CanonicalWorkOrder(
        id=id_,
        sector=sector,
        contract_value=ValueWithRaw(normalized=contract, raw=str(contract)) if contract is not None else None,
        billed_value=ValueWithRaw(normalized=billed, raw=str(billed)) if billed is not None else None,
        receivable=ValueWithRaw(normalized=receivable, raw=str(receivable)) if receivable is not None else None,
    )


def test_default_basis_is_contract_value_excl_gst():
    wos = [_wo("1", contract=100, billed=118)]
    result = analyze_revenue(wos)
    assert result.basis_used == RevenueBasis.CONTRACT_EXCL_GST
    assert result.total == 100
    assert "excl. gst" in result.basis_label.lower()


def test_explicit_basis_overrides_default():
    wos = [_wo("1", contract=100, billed=118)]
    result = analyze_revenue(wos, requested_basis=RevenueBasis.BILLED_INCL_GST)
    assert result.total == 118


def test_never_bare_revenue_always_labeled():
    result = analyze_revenue([_wo("1", contract=100)])
    assert result.basis_label  # always present and non-empty


def test_excluded_count_for_missing_basis_field():
    wos = [_wo("1", contract=100), _wo("2", contract=None)]
    result = analyze_revenue(wos)
    assert result.excluded_count == 1
    assert result.total == 100


def test_by_sector_breakdown():
    wos = [_wo("1", contract=100, sector="Energy"), _wo("2", contract=50, sector="Healthcare")]
    result = analyze_revenue(wos)
    assert result.by_sector == {"Energy": 100, "Healthcare": 50}


def test_infer_revenue_basis_from_phrasing():
    assert infer_revenue_basis("what's our billed revenue?") == RevenueBasis.BILLED_INCL_GST
    assert infer_revenue_basis("how much is outstanding receivable?") == RevenueBasis.RECEIVABLE
    assert infer_revenue_basis("what's our contract value?") == RevenueBasis.CONTRACT_EXCL_GST
    assert infer_revenue_basis("what's our revenue?") is None
