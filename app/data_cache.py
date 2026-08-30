import asyncio
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.canonical.board_kind import BoardKind, classify_board
from app.canonical.deal_mapper import map_deals
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder
from app.canonical.work_order_mapper import map_work_orders
from app.config import settings
from app.monday.client import MondayClient
from app.monday.pagination import fetch_all_items
from app.monday.schema import discover_schema
from app.validate.quality import DataQualityReport, build_quality_report
from app.validate.row_validity import filter_structurally_valid


class BoardFetchFailure(BaseModel):
    board: str
    reason: str


class BoardResult(BaseModel):
    """One configured board, after discovery, classification and mapping."""

    board_id: str
    board_name: str
    kind: BoardKind
    confidence: float = 0.0
    record_count: int = 0
    quality: DataQualityReport | None = None
    failure: BoardFetchFailure | None = None


class BoardCacheEntry(BaseModel):
    boards: list[BoardResult] = []
    # Records pooled across every board of a given kind. The BI layer is
    # written against "all deals" / "all work orders" rather than against a
    # particular board, so two Deals boards (e.g. one per region) simply
    # analyze as one deal set.
    deals: list[CanonicalDeal] = []
    work_orders: list[CanonicalWorkOrder] = []
    fetched_at: datetime

    @property
    def deal_boards(self) -> list[BoardResult]:
        return [b for b in self.boards if b.kind is BoardKind.DEALS and not b.failure]

    @property
    def work_order_boards(self) -> list[BoardResult]:
        return [b for b in self.boards if b.kind is BoardKind.WORK_ORDERS and not b.failure]

    @property
    def failures(self) -> list[BoardFetchFailure]:
        return [b.failure for b in self.boards if b.failure]

    def _first_failure_reason(self, kind: BoardKind) -> str | None:
        """A board that failed to fetch has no schema, so it can't be
        classified — an unclassifiable failure is reported against whichever
        kind the caller was asking for."""
        unusable = [b for b in self.boards if b.failure and b.kind is BoardKind.UNKNOWN]
        typed = [b for b in self.boards if b.failure and b.kind is kind]
        for board in typed + unusable:
            return board.failure.reason
        return None

    @property
    def deal_failure(self) -> BoardFetchFailure | None:
        """Present only when no Deals data is usable at all — either every
        Deals board failed, or none of the connected boards is a Deals board.
        Kept as a property so the tool layer's existing checks work unchanged
        regardless of how many boards are configured."""
        if self.deals:
            return None
        reason = self._first_failure_reason(BoardKind.DEALS)
        return BoardFetchFailure(board="Deals", reason=reason or "No connected board matched the Deals schema.")

    @property
    def wo_failure(self) -> BoardFetchFailure | None:
        if self.work_orders:
            return None
        reason = self._first_failure_reason(BoardKind.WORK_ORDERS)
        return BoardFetchFailure(
            board="Work Orders", reason=reason or "No connected board matched the Work Orders schema."
        )

    @property
    def deal_quality(self) -> DataQualityReport | None:
        boards = self.deal_boards
        return boards[0].quality if boards else None

    @property
    def wo_quality(self) -> DataQualityReport | None:
        boards = self.work_order_boards
        return boards[0].quality if boards else None


_cache: BoardCacheEntry | None = None
_lock = asyncio.Lock()


async def _fetch_board(board_id: str) -> tuple[BoardResult, list, list]:
    """Fetches, classifies and maps one board. Returns the board result plus
    the canonical deals / work orders it contributed."""
    client = MondayClient()
    schema_outcome = await discover_schema(client, board_id)
    if not schema_outcome.ok:
        return (
            BoardResult(
                board_id=board_id,
                board_name=board_id,
                kind=BoardKind.UNKNOWN,
                failure=BoardFetchFailure(board=board_id, reason=schema_outcome.reason),
            ),
            [],
            [],
        )

    board_name = schema_outcome.data.board_name
    items_outcome = await fetch_all_items(client, board_id)
    if not items_outcome.ok:
        return (
            BoardResult(
                board_id=board_id,
                board_name=board_name,
                kind=BoardKind.UNKNOWN,
                failure=BoardFetchFailure(board=board_name, reason=items_outcome.reason),
            ),
            [],
            [],
        )

    schema = schema_outcome.data.columns
    valid_items, dropped = filter_structurally_valid(items_outcome.data, schema)
    kind, confidence = classify_board(schema, valid_items)

    if kind is BoardKind.DEALS:
        deals = map_deals(valid_items, schema)
        quality = build_quality_report(board_name, len(items_outcome.data), dropped, deals)
        return (
            BoardResult(
                board_id=board_id,
                board_name=board_name,
                kind=kind,
                confidence=confidence,
                record_count=len(deals),
                quality=quality,
            ),
            deals,
            [],
        )

    if kind is BoardKind.WORK_ORDERS:
        work_orders = map_work_orders(valid_items, schema)
        quality = build_quality_report(board_name, len(items_outcome.data), dropped, work_orders)
        return (
            BoardResult(
                board_id=board_id,
                board_name=board_name,
                kind=kind,
                confidence=confidence,
                record_count=len(work_orders),
                quality=quality,
            ),
            [],
            work_orders,
        )

    # Unclassifiable: surfaced to the user as a connected-but-unusable board
    # rather than being guessed into one of the two kinds (§8).
    return (
        BoardResult(
            board_id=board_id,
            board_name=board_name,
            kind=BoardKind.UNKNOWN,
            confidence=confidence,
            record_count=len(valid_items),
            failure=BoardFetchFailure(
                board=board_name,
                reason="Schema matched neither the Deals nor the Work Orders model closely enough to analyze safely.",
            ),
        ),
        [],
        [],
    )


async def _fetch_and_normalize_all() -> BoardCacheEntry:
    # Fetched concurrently rather than one after another: latency is
    # dominated by the Monday round-trips, and with an arbitrary number of
    # configured boards a sequential fetch would grow linearly.
    packs = await asyncio.gather(*(_fetch_board(bid) for bid in settings.board_ids))

    boards = [pack[0] for pack in packs]
    deals = [d for pack in packs for d in pack[1]]
    work_orders = [w for pack in packs for w in pack[2]]

    return BoardCacheEntry(
        boards=boards,
        deals=deals,
        work_orders=work_orders,
        fetched_at=datetime.now(timezone.utc),
    )


async def get_cached_board_data() -> BoardCacheEntry:
    """Shared cache (not per-session — the boards are the same for every
    user of this prototype) with a short TTL. Never treat data past the TTL
    as live (system-prompt §26). Held in process memory, which is correct
    because Streamlit runs as a single long-lived process."""
    global _cache
    async with _lock:
        if _cache is None or datetime.now(timezone.utc) - _cache.fetched_at > timedelta(
            seconds=settings.board_cache_ttl_seconds
        ):
            _cache = await _fetch_and_normalize_all()
        return _cache
