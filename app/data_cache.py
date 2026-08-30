import asyncio
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.canonical.deal_mapper import map_deals
from app.canonical.models import CanonicalDeal, CanonicalWorkOrder
from app.canonical.work_order_mapper import map_work_orders
from app.config import settings
from app.kv_store import kv_available, kv_get, kv_set
from app.monday.client import MondayClient
from app.monday.pagination import fetch_all_items
from app.monday.schema import discover_schema
from app.validate.quality import DataQualityReport, build_quality_report
from app.validate.row_validity import filter_structurally_valid

_BOARD_CACHE_KEY = "skylark:board_cache"


class BoardFetchFailure(BaseModel):
    board: str
    reason: str


class BoardCacheEntry(BaseModel):
    deals: list[CanonicalDeal] = []
    work_orders: list[CanonicalWorkOrder] = []
    deal_quality: DataQualityReport | None = None
    wo_quality: DataQualityReport | None = None
    deal_failure: BoardFetchFailure | None = None
    wo_failure: BoardFetchFailure | None = None
    fetched_at: datetime


_cache: BoardCacheEntry | None = None
_lock = asyncio.Lock()


async def _fetch_and_normalize_board(board_id: str, board_label: str):
    client = MondayClient()
    schema_outcome = await discover_schema(client, board_id)
    if not schema_outcome.ok:
        return None, None, BoardFetchFailure(board=board_label, reason=schema_outcome.reason)

    items_outcome = await fetch_all_items(client, board_id)
    if not items_outcome.ok:
        return None, None, BoardFetchFailure(board=board_label, reason=items_outcome.reason)

    schema = schema_outcome.data.columns
    valid_items, dropped = filter_structurally_valid(items_outcome.data, schema)
    return schema, (valid_items, dropped, len(items_outcome.data)), None


async def _fetch_and_normalize_all() -> BoardCacheEntry:
    # Fetched in parallel, not sequentially: on Vercel Hobby the two Monday
    # round-trips plus the Gemini tool-calling loop can otherwise approach
    # the 10s function timeout (see header build instructions §4).
    (deal_schema, deal_pack, deal_failure), (wo_schema, wo_pack, wo_failure) = await asyncio.gather(
        _fetch_and_normalize_board(settings.deals_board_id, "Deals"),
        _fetch_and_normalize_board(settings.work_orders_board_id, "Work Orders"),
    )

    deals: list[CanonicalDeal] = []
    deal_quality = None
    if deal_pack:
        valid_items, dropped, total_fetched = deal_pack
        deals = map_deals(valid_items, deal_schema)
        deal_quality = build_quality_report("Deals", total_fetched, dropped, deals)

    work_orders: list[CanonicalWorkOrder] = []
    wo_quality = None
    if wo_pack:
        valid_items, dropped, total_fetched = wo_pack
        work_orders = map_work_orders(valid_items, wo_schema)
        wo_quality = build_quality_report("Work Orders", total_fetched, dropped, work_orders)

    return BoardCacheEntry(
        deals=deals,
        work_orders=work_orders,
        deal_quality=deal_quality,
        wo_quality=wo_quality,
        deal_failure=deal_failure,
        wo_failure=wo_failure,
        fetched_at=datetime.now(timezone.utc),
    )


async def get_cached_board_data() -> BoardCacheEntry:
    """Shared cache (not per-session — both boards are the same for every
    user of this prototype) with a short TTL. Never treat data past the TTL
    as live (system-prompt §26).

    Backed by Vercel KV / Upstash Redis when KV_REST_API_URL and
    KV_REST_API_TOKEN are set, since a serverless function's process memory
    does not survive between invocations. Falls back to a module-global dict
    (correct only for a single long-lived process, e.g. local `uvicorn` dev)
    when they aren't."""
    global _cache
    async with _lock:
        if kv_available():
            raw = await kv_get(_BOARD_CACHE_KEY)
            if raw is not None:
                return BoardCacheEntry.model_validate_json(raw)
            entry = await _fetch_and_normalize_all()
            await kv_set(_BOARD_CACHE_KEY, entry.model_dump_json(), ex_seconds=settings.board_cache_ttl_seconds)
            return entry

        if _cache is None or datetime.now(timezone.utc) - _cache.fetched_at > timedelta(
            seconds=settings.board_cache_ttl_seconds
        ):
            _cache = await _fetch_and_normalize_all()
        return _cache
