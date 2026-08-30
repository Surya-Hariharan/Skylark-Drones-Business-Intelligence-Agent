from app.canonical.deal_mapper import map_deals
from app.canonical.work_order_mapper import map_work_orders
from app.monday.pagination import RawItem
from app.monday.schema import ColumnDef

DEAL_SCHEMA = [
    ColumnDef(id="c_name", title="Deal Name", type="text"),
    ColumnDef(id="c_owner", title="Owner code", type="text"),
    ColumnDef(id="c_client", title="Client Code", type="text"),
    ColumnDef(id="c_status", title="Deal Status", type="status"),
    ColumnDef(id="c_close_a", title="Close Date (A)", type="date"),
    ColumnDef(id="c_conf", title="Closure Probability", type="status"),
    ColumnDef(id="c_value", title="Masked Deal value", type="numbers"),
    ColumnDef(id="c_tentative", title="Tentative Close Date", type="date"),
    ColumnDef(id="c_stage", title="Deal Stage", type="text"),
    ColumnDef(id="c_product", title="Product deal", type="text"),
    ColumnDef(id="c_sector", title="Sector/service", type="text"),
    ColumnDef(id="c_created", title="Created Date", type="date"),
]


def _deal_item(item_id, **overrides):
    values = {
        "c_name": "Sasuke",
        "c_owner": "OWNER_001",
        "c_client": "COMPANY001",
        "c_status": "Open",
        "c_close_a": None,
        "c_conf": "High",
        "c_value": "1,500,000",
        "c_tentative": "2026-06-01",
        "c_stage": "C",
        "c_product": "Survey",
        "c_sector": "Energy",
        "c_created": "2026-01-01",
    }
    values.update(overrides)
    return RawItem(id=item_id, name=values.pop("c_name", "Sasuke"), column_values={
        k: {"text": v, "value": None} for k, v in values.items()
    })


def test_map_deals_populates_known_fields():
    item = _deal_item("1")
    deals = map_deals([item], DEAL_SCHEMA)
    assert len(deals) == 1
    deal = deals[0]
    assert deal.owner_id == "OWNER_001"
    assert deal.client_id == "COMPANY001"
    assert deal.status == "Open"
    assert deal.close_confidence == "High"
    assert deal.value is not None and deal.value.normalized == 1_500_000.0
    assert deal.sector == "Energy"
    assert deal.stage == "C"


def test_map_deals_missing_value_is_none_not_zero():
    item = _deal_item("2", c_value=None)
    deal = map_deals([item], DEAL_SCHEMA)[0]
    assert deal.value is None


def test_map_deals_preserves_raw_row():
    item = _deal_item("3")
    deal = map_deals([item], DEAL_SCHEMA)[0]
    assert deal.raw_row  # never discarded


WO_SCHEMA = [
    ColumnDef(id="w_deal_name", title="Deal name masked", type="text"),
    ColumnDef(id="w_client", title="Customer Name Code", type="text"),
    ColumnDef(id="w_status", title="Execution Status", type="text"),
    ColumnDef(id="w_sector", title="Sector", type="text"),
    ColumnDef(id="w_contract", title="Amount in Rupees (Excl of GST) (Masked)", type="numbers"),
    ColumnDef(id="w_billed", title="Billed Value (Incl GST) (Masked)", type="numbers"),
    ColumnDef(id="w_receivable", title="Amount Receivable (Masked)", type="numbers"),
    ColumnDef(id="w_invoice", title="Invoice Status", type="text"),
    ColumnDef(id="w_billing", title="WO Status (billed)", type="status"),
    ColumnDef(id="w_ar", title="AR Priority account", type="text"),
    ColumnDef(id="w_start", title="Probable Start Date", type="date"),
    ColumnDef(id="w_end", title="Probable End Date", type="date"),
]


def _wo_item(item_id, **overrides):
    values = {
        "w_deal_name": "Sasuke",
        "w_client": "WOCOMPANY_001",
        "w_status": "Executed until current month",
        "w_sector": "Energy",
        "w_contract": "2,000,000",
        "w_billed": "2,360,000",
        "w_receivable": "500,000",
        "w_invoice": "Billed- Visit 7",
        "w_billing": "Open",
        "w_ar": None,
        "w_start": "2026-01-15",
        "w_end": "2026-05-15",
    }
    values.update(overrides)
    return RawItem(id=item_id, name="WO", column_values={k: {"text": v, "value": None} for k, v in values.items()})


def test_map_work_orders_populates_known_fields_and_keeps_distinct_statuses():
    item = _wo_item("1")
    wo = map_work_orders([item], WO_SCHEMA)[0]
    assert wo.client_id == "WOCOMPANY_001"
    assert wo.status == "Executed until current month"  # not collapsed into a generic "completed"
    assert wo.sector == "Energy"
    assert wo.contract_value.normalized == 2_000_000.0
    assert wo.billed_value.normalized == 2_360_000.0
    assert wo.receivable.normalized == 500_000.0
    assert wo.billing_status == "Open"


def test_deal_and_work_order_client_id_schemes_are_not_conflated():
    deal = map_deals([_deal_item("1")], DEAL_SCHEMA)[0]
    wo = map_work_orders([_wo_item("1")], WO_SCHEMA)[0]
    assert deal.client_id != wo.client_id
    assert deal.client_id == "COMPANY001"
    assert wo.client_id == "WOCOMPANY_001"
