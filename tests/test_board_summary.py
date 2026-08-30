from datetime import datetime, timezone

from app.board_summary import build_board_summaries, render_session_context_block
from app.canonical.board_kind import BoardKind
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder
from app.data_cache import BoardCacheEntry, BoardFetchFailure, BoardResult
from app.validate.quality import build_quality_report


def _entry(**kwargs) -> BoardCacheEntry:
    return BoardCacheEntry(fetched_at=datetime.now(timezone.utc), **kwargs)


def _deal_board(deals, name="Deals") -> BoardResult:
    quality = build_quality_report(
        name, total_fetched=len(deals), structurally_invalid_dropped=0, canonical_records=deals
    )
    return BoardResult(
        board_id="1", board_name=name, kind=BoardKind.DEALS, record_count=len(deals), quality=quality
    )


def _wo_board(work_orders, name="Work Orders") -> BoardResult:
    quality = build_quality_report(
        name, total_fetched=len(work_orders), structurally_invalid_dropped=0, canonical_records=work_orders
    )
    return BoardResult(
        board_id="2",
        board_name=name,
        kind=BoardKind.WORK_ORDERS,
        record_count=len(work_orders),
        quality=quality,
    )


def test_connected_board_reports_dropped_and_low_fill_flags():
    deals = [
        CanonicalDeal(id="1", name="A", sector="Mining", close_confidence=None),
        CanonicalDeal(id="2", name="B", sector="Mining", close_confidence="High"),
        CanonicalDeal(id="3", name="C", sector="Renewables", close_confidence=None),
        CanonicalDeal(id="4", name="D", sector="Renewables", close_confidence=None),
    ]
    entry = _entry(deals=deals, boards=[_deal_board(deals)])

    summaries = build_board_summaries(entry)
    deals_summary = next(s for s in summaries if s.name == "Deals")

    assert deals_summary.connected is True
    assert deals_summary.record_count == 4
    assert deals_summary.kind == "deals"
    assert "sector" in deals_summary.fields
    assert any("owner_id missing on all records" in f for f in deals_summary.flags)
    assert any("close_confidence missing on 75% of records" in f for f in deals_summary.flags)


def test_disconnected_board_reports_failure_not_stats():
    entry = _entry(
        boards=[
            BoardResult(
                board_id="1",
                board_name="Deals",
                kind=BoardKind.UNKNOWN,
                failure=BoardFetchFailure(board="Deals", reason="401 Unauthorized"),
            )
        ]
    )

    summaries = build_board_summaries(entry)
    deals_summary = next(s for s in summaries if s.name == "Deals")

    assert deals_summary.connected is False
    assert deals_summary.record_count == 0
    assert deals_summary.failure_reason == "401 Unauthorized"


def test_high_fill_sector_flagged_as_best_cross_board_field():
    work_orders = [CanonicalWorkOrder(id=str(i), sector="Mining") for i in range(10)]
    entry = _entry(work_orders=work_orders, boards=[_wo_board(work_orders)])

    summaries = build_board_summaries(entry)
    wo_summary = next(s for s in summaries if s.name == "Work Orders")

    assert any("best cross-board comparison field" in f for f in wo_summary.flags)


def test_session_context_block_lists_sector_sample_and_failure():
    deals = [
        CanonicalDeal(id="1", name="A", sector="Mining"),
        CanonicalDeal(id="2", name="B", sector="Renewables"),
    ]
    entry = _entry(
        deals=deals,
        boards=[
            _deal_board(deals),
            BoardResult(
                board_id="2",
                board_name="Work Orders",
                kind=BoardKind.UNKNOWN,
                failure=BoardFetchFailure(board="Work Orders", reason="timed out"),
            ),
        ],
    )

    block = render_session_context_block(entry)

    assert "Connected boards this session: 2 configured." in block
    assert "Deals: read as deals, 2 records, sectors: Mining/Renewables" in block
    assert "Work Orders: NOT USABLE (timed out)" in block


def test_arbitrary_number_of_boards_each_summarized():
    """Two Deals boards plus one Work Orders board — nothing about the
    summary layer assumes exactly two boards, or a fixed ordering."""
    north = [CanonicalDeal(id="1", name="A", sector="Mining")]
    south = [CanonicalDeal(id="2", name="B", sector="Roads")]
    work_orders = [CanonicalWorkOrder(id="3", sector="Mining")]
    entry = _entry(
        deals=north + south,
        work_orders=work_orders,
        boards=[
            _deal_board(north, name="Deals North"),
            _deal_board(south, name="Deals South"),
            _wo_board(work_orders),
        ],
    )

    summaries = build_board_summaries(entry)

    assert [s.name for s in summaries] == ["Deals North", "Deals South", "Work Orders"]
    assert all(s.connected for s in summaries)


def test_capabilities_narrow_when_only_deals_connected():
    deals = [CanonicalDeal(id="1", name="A", sector="Mining")]
    entry = _entry(deals=deals, boards=[_deal_board(deals)])

    block = render_session_context_block(entry)

    assert "pipeline and deal-side sector performance ONLY" in block
    assert "revenue, operations, cross-board" in block


def test_capabilities_full_when_both_kinds_connected():
    deals = [CanonicalDeal(id="1", name="A", sector="Mining")]
    work_orders = [CanonicalWorkOrder(id="2", sector="Mining")]
    entry = _entry(
        deals=deals, work_orders=work_orders, boards=[_deal_board(deals), _wo_board(work_orders)]
    )

    block = render_session_context_block(entry)

    assert "all tools, including cross-board" in block
    assert "only be joined on sector" in block


def test_no_usable_data_forbids_numeric_answers():
    entry = _entry(
        boards=[
            BoardResult(
                board_id="1",
                board_name="Mystery",
                kind=BoardKind.UNKNOWN,
                failure=BoardFetchFailure(board="Mystery", reason="schema unrecognized"),
            )
        ]
    )

    block = render_session_context_block(entry)

    assert "NO usable business data is connected" in block


def test_failure_properties_reflect_missing_kind():
    """A board kind that simply isn't connected reads as a failure to the
    tool layer, so tools refuse rather than computing on an empty list."""
    deals = [CanonicalDeal(id="1", name="A", sector="Mining")]
    entry = _entry(deals=deals, boards=[_deal_board(deals)])

    assert entry.deal_failure is None
    assert entry.wo_failure is not None
    assert "No connected board matched" in entry.wo_failure.reason
