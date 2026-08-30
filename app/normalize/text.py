from pydantic import BaseModel


class TextResult(BaseModel):
    value: str | None
    raw: str


def normalize_text(raw, alias_table: dict[str, str] | None = None) -> TextResult:
    """Trims whitespace and collapses obvious casing variants via an explicit
    alias table (matched case-insensitively). Unknown values are preserved
    as-is rather than being forced into an existing category."""
    raw_str = "" if raw is None else str(raw)
    trimmed = " ".join(raw_str.split())
    if not trimmed:
        return TextResult(value=None, raw=raw_str)

    if alias_table:
        lowered = trimmed.lower()
        for alias, canonical in alias_table.items():
            if alias.lower() == lowered:
                return TextResult(value=canonical, raw=raw_str)

    return TextResult(value=trimmed, raw=raw_str)
