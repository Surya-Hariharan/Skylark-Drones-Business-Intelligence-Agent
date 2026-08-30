from app.canonical.board_kind import BoardKind, classify_board
from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef

DEAL_SCHEMA = [
    ColumnDef(id="c_name", title="Deal Name", type="text"),
    ColumnDef(id="c_owner", title="Owner code", type="text"),
    ColumnDef(id="c_status", title="Deal Status", type="status"),
    ColumnDef(id="c_conf", title="Closure Probability", type="status"),
    ColumnDef(id="c_value", title="Masked Deal value", type="numbers"),
    ColumnDef(id="c_tentative", title="Tentative Close Date", type="date"),
    ColumnDef(id="c_stage", title="Deal Stage", type="text"),
    ColumnDef(id="c_sector", title="Sector/service", type="text"),
]

WORK_ORDER_SCHEMA = [
    ColumnDef(id="w_deal", title="Deal name masked", type="text"),
    ColumnDef(id="w_client", title="Customer Name Code", type="text"),
    ColumnDef(id="w_status", title="Execution Status", type="status"),
    ColumnDef(id="w_sector", title="Sector", type="text"),
    ColumnDef(id="w_contract", title="Amount in Rupees (Excl of GST) (Masked)", type="numbers"),
    ColumnDef(id="w_billed", title="Billed Value (Incl GST) (Masked)", type="numbers"),
    ColumnDef(id="w_recv", title="Amount Receivable (Masked)", type="numbers"),
    ColumnDef(id="w_invoice", title="Invoice Status", type="text"),
    ColumnDef(id="w_ar", title="AR Priority account", type="text"),
]


def _item(item_id: str, values: dict) -> RawItem:
    return RawItem(
        id=item_id,
        name=f"item-{item_id}",
        column_values={k: {"text": v, "value": None} for k, v in values.items()},
    )


def _deal_items(n=5):
    return [
        _item(
            str(i),
            {
                "c_name": "Sasuke",
                "c_owner": "OWNER_001",
                "c_status": "Open",
                "c_conf": "High",
                "c_value": "1500000",
                "c_tentative": "2026-01-01",
                "c_stage": "A. Lead Generated",
                "c_sector": "Mining",
            },
        )
        for i in range(n)
    ]


def _work_order_items(n=5):
    return [
        _item(
            str(i),
            {
                "w_deal": "Sasuke",
                "w_client": "COMPANY001",
                "w_status": "Completed",
                "w_sector": "Mining",
                "w_contract": "500000",
                "w_billed": "590000",
                "w_recv": "90000",
                "w_invoice": "Raised",
                "w_ar": "Yes",
            },
        )
        for i in range(n)
    ]


def test_deals_board_classified_as_deals():
    kind, confidence = classify_board(DEAL_SCHEMA, _deal_items())
    assert kind is BoardKind.DEALS
    assert confidence > 0.5


def test_work_orders_board_classified_as_work_orders():
    kind, confidence = classify_board(WORK_ORDER_SCHEMA, _work_order_items())
    assert kind is BoardKind.WORK_ORDERS
    assert confidence > 0.5


def test_classification_ignores_configured_order():
    """The kind comes from the board's own schema, so classifying the same
    two boards in either order gives the same answer — position in
    MONDAY_BOARD_IDS carries no meaning."""
    first = classify_board(WORK_ORDER_SCHEMA, _work_order_items())[0]
    second = classify_board(DEAL_SCHEMA, _deal_items())[0]
    assert (first, second) == (BoardKind.WORK_ORDERS, BoardKind.DEALS)


def test_unrelated_board_is_unknown_not_forced():
    """A board matching neither model must stay UNKNOWN — guessing it into
    whichever kind scored marginally higher would silently corrupt every
    downstream metric."""
    schema = [
        ColumnDef(id="x_title", title="Ticket Title", type="text"),
        ColumnDef(id="x_assignee", title="Assignee", type="people"),
        ColumnDef(id="x_priority", title="Priority", type="status"),
    ]
    items = [
        _item(str(i), {"x_title": "Fix login", "x_assignee": "Ana", "x_priority": "P1"}) for i in range(5)
    ]

    kind, _ = classify_board(schema, items)
    assert kind is BoardKind.UNKNOWN


def test_empty_board_is_unknown():
    kind, _ = classify_board([], [])
    assert kind is BoardKind.UNKNOWN
