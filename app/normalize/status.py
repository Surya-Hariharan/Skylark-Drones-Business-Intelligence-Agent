from pydantic import BaseModel


class StatusResult(BaseModel):
    value: str | None
    raw: str


def normalize_status(raw, domain: list[str]) -> StatusResult:
    """Case/whitespace-insensitive match against a known domain of statuses
    (e.g. ["Won", "Dead", "Open", "On Hold"]). An unmatched value is preserved
    in `raw` but `value` is left None rather than guessed."""
    raw_str = "" if raw is None else str(raw)
    trimmed = " ".join(raw_str.split())
    if not trimmed:
        return StatusResult(value=None, raw=raw_str)

    lowered = trimmed.lower()
    for candidate in domain:
        if candidate.lower() == lowered:
            return StatusResult(value=candidate, raw=raw_str)

    return StatusResult(value=None, raw=raw_str)
