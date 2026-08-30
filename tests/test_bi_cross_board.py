import inspect

from app.bi import cross_board
from app.bi.cross_board import analyze_cross_board
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder, ValueWithRaw


def test_cross_board_never_references_client_id_or_deal_name_matching():
    source = inspect.getsource(cross_board)
    assert "client_id" not in source
    assert "deal_name" not in source


def test_cross_board_always_carries_join_caveat():
    deals = [CanonicalDeal(id="1", name="A", sector="Energy", status="Open")]
    wos = [CanonicalWorkOrder(id="1", sector="Energy")]
    result = analyze_cross_board(deals, wos)
    assert result.join_key == "sector"
    assert "sector level" in result.join_caveat.lower()


def test_cross_board_groups_by_union_of_sectors():
    deals = [CanonicalDeal(id="1", name="A", sector="Energy", status="Open")]
    wos = [CanonicalWorkOrder(id="1", sector="Healthcare")]
    result = analyze_cross_board(deals, wos)
    sectors = {s.sector for s in result.by_sector}
    assert sectors == {"Energy", "Healthcare"}
