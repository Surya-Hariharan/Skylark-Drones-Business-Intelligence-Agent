from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ValueWithRaw(BaseModel):
    normalized: float
    unit: str | None = None
    raw: str


class CanonicalDeal(BaseModel):
    id: str
    name: str
    owner_id: str | None = None
    client_id: str | None = None
    status: str | None = None
    stage: str | None = None
    value: ValueWithRaw | None = None
    close_confidence: Literal["High", "Medium", "Low"] | None = None
    expected_close_date: date | None = None
    actual_close_date: date | None = None
    created_date: date | None = None
    sector: str | None = None
    product_type: str | None = None
    # Named `raw_row` (not `_raw`) because Pydantic v2 treats leading-underscore
    # field names as PrivateAttr, which breaks normal serialization.
    raw_row: dict = Field(default_factory=dict)


class CanonicalWorkOrder(BaseModel):
    id: str
    deal_name: str | None = None
    client_id: str | None = None
    status: str | None = None
    sector: str | None = None
    contract_value: ValueWithRaw | None = None  # Amount Excl GST
    billed_value: ValueWithRaw | None = None  # Incl GST
    receivable: ValueWithRaw | None = None
    invoice_status: str | None = None
    billing_status: Literal["Open", "Closed"] | None = None
    ar_priority: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    raw_row: dict = Field(default_factory=dict)
