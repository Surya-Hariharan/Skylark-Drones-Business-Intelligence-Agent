import re
from datetime import date, datetime

from dateutil import parser as dateutil_parser
from pydantic import BaseModel

_AMBIGUOUS_SLASH_OR_DASH = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s*")
_ISO_PREFIX = re.compile(r"^\s*\d{4}-\d{2}-\d{2}")


class DateResult(BaseModel):
    date: date | None
    ambiguous: bool
    raw: str


def normalize_date(raw: str | None) -> DateResult:
    """Never guesses. ISO-style (YYYY-MM-DD[...]) and unambiguous formats are
    parsed. A DD/MM vs MM/DD-style date where both components are <=12 is
    reported as ambiguous rather than silently assumed one way or the other."""
    if raw is None or not str(raw).strip():
        return DateResult(date=None, ambiguous=False, raw=str(raw) if raw is not None else "")

    text = str(raw).strip()

    if _ISO_PREFIX.match(text):
        try:
            return DateResult(date=dateutil_parser.parse(text).date(), ambiguous=False, raw=text)
        except (ValueError, OverflowError):
            return DateResult(date=None, ambiguous=False, raw=text)

    match = _AMBIGUOUS_SLASH_OR_DASH.match(text)
    if match:
        first, second, _year = int(match.group(1)), int(match.group(2)), match.group(3)
        if first <= 12 and second <= 12 and first != second:
            return DateResult(date=None, ambiguous=True, raw=text)
        try:
            return DateResult(date=dateutil_parser.parse(text, dayfirst=first > 12).date(), ambiguous=False, raw=text)
        except (ValueError, OverflowError):
            return DateResult(date=None, ambiguous=False, raw=text)

    try:
        return DateResult(date=dateutil_parser.parse(text).date(), ambiguous=False, raw=text)
    except (ValueError, OverflowError, TypeError):
        return DateResult(date=None, ambiguous=False, raw=text)
