from datetime import datetime, timezone

from app.board_summary import build_board_summaries, render_session_context_block
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder
from app.data_cache import BoardCacheEntry, BoardFetchFailure
from app.validate.quality import build_quality_report


def _entry(**kwargs) -> BoardCacheEntry:
    return BoardCacheEntry(fetched_at=datetime.now(timezone.utc), **kwargs)


def test_connected_board_reports_dropped_and_low_fill_flags():
    deals = [
        CanonicalDeal(id="1", name="A", sector="Mining", close_confidence=None),
        CanonicalDeal(id="2", name="B", sector="Mining", close_confidence="High"),
        CanonicalDeal(id="3", name="C", sector="Renewables", close_confidence=None),
        CanonicalDeal(id="4", name="D", sector="Renewables", close_confidence=None),
    ]
    quality = build_quality_report("Deals", total_fetched=4, structurally_invalid_dropped=0, canonical_records=deals)
    entry = _entry(deals=deals, deal_quality=quality)

    summaries = build_board_summaries(entry)
    deals_summary = next(s for s in summaries if s.name == "Deals")

    assert deals_summary.connected is True
    assert deals_summary.record_count == 4
    assert "sector" in deals_summary.fields
    assert any("owner_id missing on all records" in f for f in deals_summary.flags)
    assert any("close_confidence missing on 75% of records" in f for f in deals_summary.flags)


def test_disconnected_board_reports_failure_not_stats():
    entry = _entry(deal_failure=BoardFetchFailure(board="Deals", reason="401 Unauthorized"))

    summaries = build_board_summaries(entry)
    deals_summary = next(s for s in summaries if s.name == "Deals")

    assert deals_summary.connected is False
    assert deals_summary.record_count == 0
    assert deals_summary.failure_reason == "401 Unauthorized"


def test_high_fill_sector_flagged_as_best_cross_board_field():
    work_orders = [CanonicalWorkOrder(id=str(i), sector="Mining") for i in range(10)]
    quality = build_quality_report(
        "Work Orders", total_fetched=10, structurally_invalid_dropped=0, canonical_records=work_orders
    )
    entry = _entry(work_orders=work_orders, wo_quality=quality)

    summaries = build_board_summaries(entry)
    wo_summary = next(s for s in summaries if s.name == "Work Orders")

    assert any("best cross-board comparison field" in f for f in wo_summary.flags)


def test_session_context_block_lists_sector_sample_and_failure():
    deals = [
        CanonicalDeal(id="1", name="A", sector="Mining"),
        CanonicalDeal(id="2", name="B", sector="Renewables"),
    ]
    quality = build_quality_report("Deals", total_fetched=2, structurally_invalid_dropped=0, canonical_records=deals)
    entry = _entry(
        deals=deals,
        deal_quality=quality,
        wo_failure=BoardFetchFailure(board="Work Orders", reason="timed out"),
    )

    block = render_session_context_block(entry)

    assert "Connected boards this session:" in block
    assert "Deals: 2 records, sectors: Mining/Renewables" in block
    assert "Work Orders: NOT CONNECTED (timed out)" in block
