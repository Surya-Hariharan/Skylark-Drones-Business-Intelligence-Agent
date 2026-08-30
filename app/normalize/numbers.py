import re

from pydantic import BaseModel

_NUMBER_UNIT_PATTERN = re.compile(
    r"^\s*[₹$€£]?\s*(-?[\d,]+(?:\.\d+)?)\s*%?\s*([A-Za-z]+)?\s*$"
)


class NumberResult(BaseModel):
    value: float | None
    unit: str | None
    raw: str


def normalize_number(raw) -> NumberResult:
    """Extracts a numeric value plus an optional trailing unit (e.g. "5,360 HA"
    -> value=5360.0, unit="HA"). Never converts missing/unparseable input to 0 —
    that would conflate "unknown" with "genuinely zero"."""
    raw_str = "" if raw is None else str(raw)
    text = raw_str.strip()
    if not text:
        return NumberResult(value=None, unit=None, raw=raw_str)

    match = _NUMBER_UNIT_PATTERN.match(text)
    if not match:
        return NumberResult(value=None, unit=None, raw=raw_str)

    number_part, unit_part = match.group(1), match.group(2)
    cleaned = number_part.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return NumberResult(value=None, unit=None, raw=raw_str)

    return NumberResult(value=value, unit=unit_part or None, raw=raw_str)
