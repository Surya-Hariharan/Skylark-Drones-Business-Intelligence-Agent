"""Infers what kind of business data a board holds from its own discovered
schema, rather than from which config slot it was listed in.

The agent accepts an arbitrary list of board IDs (`MONDAY_BOARD_IDS`), so
position carries no meaning — board #2 is not necessarily Work Orders. Each
board is classified by asking how much of each mapper's field spec actually
resolves against that board's columns, which reuses the same alias +
type/value-shape matching the mappers themselves use (system-prompt §3:
discover the schema, never assume fixed names or ordering).

A board that matches neither well enough is left UNKNOWN and excluded from
analysis rather than being forced into whichever kind scored marginally
higher — a misclassified board would silently corrupt every downstream
metric, which is worse than reporting the board as unusable (§8).
"""
from enum import Enum

from app.canonical.deal_mapper import DEAL_FIELD_SPECS
from app.canonical.mapping_utils import resolve_column_mapping
from app.canonical.work_order_mapper import WORK_ORDER_FIELD_SPECS
from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef

# Fields that only make sense on one of the two board kinds. Deliberately
# excludes fields both boards share (name, client_id, sector, status), which
# carry no discriminating signal.
_DEAL_SIGNATURE = frozenset({"stage", "close_confidence", "expected_close_date", "owner_id", "value"})
_WORK_ORDER_SIGNATURE = frozenset(
    {"contract_value", "billed_value", "receivable", "invoice_status", "billing_status", "ar_priority"}
)

# A board must resolve at least this share of one kind's signature fields to
# be classified as that kind, and beat the other kind by at least this
# margin. Both are judgment calls, set so that a board matching two or three
# signature fields by coincidence stays UNKNOWN.
_MIN_SCORE = 0.34
_MIN_MARGIN = 0.15


class BoardKind(str, Enum):
    DEALS = "deals"
    WORK_ORDERS = "work_orders"
    UNKNOWN = "unknown"


def _signature_score(
    schema: list[ColumnDef], items: list[RawItem], specs, signature: frozenset[str]
) -> float:
    mapping = resolve_column_mapping(schema, items, specs)
    return len(signature & mapping.keys()) / len(signature)


def classify_board(schema: list[ColumnDef], items: list[RawItem]) -> tuple[BoardKind, float]:
    """Returns the inferred kind and the winning confidence score (0-1)."""
    deal_score = _signature_score(schema, items, DEAL_FIELD_SPECS, _DEAL_SIGNATURE)
    wo_score = _signature_score(schema, items, WORK_ORDER_FIELD_SPECS, _WORK_ORDER_SIGNATURE)

    if deal_score >= _MIN_SCORE and deal_score - wo_score >= _MIN_MARGIN:
        return BoardKind.DEALS, deal_score
    if wo_score >= _MIN_SCORE and wo_score - deal_score >= _MIN_MARGIN:
        return BoardKind.WORK_ORDERS, wo_score
    return BoardKind.UNKNOWN, max(deal_score, wo_score)
