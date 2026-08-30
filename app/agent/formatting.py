import re
from typing import Any, Literal

from pydantic import BaseModel

_DUPLICATE_HEADER_RE = re.compile(
    r"(?:^|\n)\s*#{1,4}\s*(answer|key metrics|insight|data quality)\b",
    re.IGNORECASE,
)
_ANY_HEADER_RE = re.compile(r"(?:^|\n)\s*#{1,4}\s*([^\n]+)")
_LEADERSHIP_ALLOWED_HEADERS = {"executive summary", "key takeaway"}
_FALLBACK_INSIGHT = "See the metrics above for the full breakdown."


def _strip_duplicated_structure(insight_text: str) -> str:
    """Defends the §20/§21 formatting boundary at the code layer, not just
    via instruction: if the model's final turn re-emits its own Answer/Key
    metrics/Data quality section headers (duplicating what render_metrics
    already renders from the typed tool result, instead of writing only the
    Insight paragraph as instructed), keep only the prose written before the
    first such heading rather than showing the duplicated structure."""
    match = _DUPLICATE_HEADER_RE.search(insight_text)
    if not match:
        return insight_text.strip()
    stripped = insight_text[: match.start()].strip()
    return stripped or _FALLBACK_INSIGHT


def _extract_leadership_insight(insight_text: str) -> str:
    """generate_leadership_update's Insight is meant to be ONLY the Executive
    Summary and Key Takeaway prose: system-prompt §23 lists a full
    seven-section leadership-update structure, but the implementation note
    narrows the model's actual job to just these two sections — Pipeline /
    Operations / Financial / Sector Highlights / Risks are already rendered
    from typed data via render_metrics's `metrics`/`caveats`. In practice the
    model tends to follow §23's fuller structure anyway, so keep only the
    text under an Executive Summary or Key Takeaway heading (in whichever
    order/spacing they appear) and drop every other section it adds."""
    headers = list(_ANY_HEADER_RE.finditer(insight_text))
    if not headers:
        return insight_text.strip()

    kept: list[str] = []
    lead = insight_text[: headers[0].start()].strip()
    if lead:
        kept.append(lead)

    for i, header in enumerate(headers):
        title = header.group(1).strip()
        if title.lower() not in _LEADERSHIP_ALLOWED_HEADERS:
            continue
        end = headers[i + 1].start() if i + 1 < len(headers) else len(insight_text)
        body = insight_text[header.end():end].strip()
        if body:
            kept.append(f"**{title}**\n\n{body}")

    return "\n\n".join(kept).strip() or _FALLBACK_INSIGHT


class ChatResponse(BaseModel):
    answer: str
    metrics: list[str]
    insight: str
    caveats: list[str]
    confidence: Literal["High", "Medium", "Low"]


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "not available"
    return f"₹{v:,.0f}"


def render_metrics(tool_name: str, result: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Deterministically renders the Answer line, Key-metrics lines, and
    caveats directly from a tool's structured result — no LLM involvement.
    This is the code half of the §20/§21 calculate-vs-explain split."""
    caveats = list(result.get("caveats", []))

    if tool_name == "analyze_pipeline":
        answer = f"Open pipeline: {result['total_open_deals']} deals, {_fmt_money(result['total_open_value'])}"
        metrics = [
            f"Open deals: {result['total_open_deals']}",
            f"Open pipeline value: {_fmt_money(result['total_open_value'])}",
        ]
        metrics += [f"Stage — {k}: {v}" for k, v in result["by_stage"].items()]
        metrics += [f"Closure confidence — {k}: {v}" for k, v in result["by_close_confidence"].items()]
        if result["unclassified_confidence_count"]:
            metrics.append(f"Unclassified confidence: {result['unclassified_confidence_count']}")
        return answer, metrics, caveats

    if tool_name == "analyze_revenue":
        answer = f"{result['basis_label']}: {_fmt_money(result['total'])}"
        metrics = [f"{result['basis_label']} (total): {_fmt_money(result['total'])}"]
        metrics += [f"{sector}: {_fmt_money(v)}" for sector, v in result["by_sector"].items()]
        return answer, metrics, caveats

    if tool_name == "analyze_operations":
        answer = f"{result['total_work_orders']} work orders"
        metrics = [f"Total work orders: {result['total_work_orders']}"]
        metrics += [f"Status — {k}: {v}" for k, v in result["by_status"].items()]
        metrics += [f"Billing — {k}: {v}" for k, v in result["by_billing_status"].items()]
        metrics.append(f"AR priority accounts: {result['ar_priority_count']}")
        return answer, metrics, caveats

    if tool_name == "analyze_sector_performance":
        sector_label = result["sector"] or "Overall"
        answer = f"{sector_label}: {result['deal_count']} deals, {result['work_order_count']} work orders"
        metrics = [
            f"Sector: {sector_label}",
            f"Deal count: {result['deal_count']}",
            f"Open pipeline value: {_fmt_money(result['open_pipeline_value'])}",
            f"Work order count: {result['work_order_count']}",
        ]
        if result["revenue_total"] is not None:
            metrics.append(f"{result['revenue_basis_label']}: {_fmt_money(result['revenue_total'])}")
        return answer, metrics, caveats

    if tool_name == "analyze_cross_board":
        answer = "Sector-level pipeline vs. execution comparison"
        metrics = [
            f"{s['sector']}: pipeline {_fmt_money(s['open_pipeline_value'])}, {s['work_order_count']} work orders"
            for s in result["by_sector"]
        ]
        caveats = [result["join_caveat"]] + caveats
        return answer, metrics, caveats

    if tool_name == "generate_leadership_update":
        pipeline, operations, financial = result["pipeline"], result["operations"], result["financial"]
        answer = "Leadership update"
        metrics = [
            f"Open pipeline: {pipeline['total_open_deals']} deals, {_fmt_money(pipeline['total_open_value'])}",
            f"Work orders: {operations['total_work_orders']}",
            f"{financial['basis_label']}: {_fmt_money(financial['total'])}",
        ]
        metrics += [
            f"Top sector — {s['sector']}: pipeline {_fmt_money(s['open_pipeline_value'])}"
            for s in result["sector_highlights"][:3]
        ]
        caveats = list(result["risks_and_attention"]) + caveats
        return answer, metrics, caveats

    return "", [], caveats


def classify_confidence(tool_name: str, result: dict[str, Any], board_caveats: list[str]) -> Literal["High", "Medium", "Low"]:
    """Internal High/Medium/Low classification per system-prompt §25 — a
    simple, explainable heuristic based on how much of the relevant data
    was usable, not a learned score."""
    if board_caveats:
        return "Low"
    if tool_name == "analyze_cross_board":
        return "Medium"  # sector-only join is inherently an approximation

    excluded = result.get("excluded_count")
    denominators = {
        "analyze_pipeline": result.get("total_open_deals"),
        "analyze_revenue": None,
        "analyze_operations": result.get("total_work_orders"),
    }
    total = denominators.get(tool_name)
    if tool_name == "analyze_revenue" and result.get("by_sector") is not None:
        total = (excluded or 0) + len(result["by_sector"])

    if excluded and total:
        ratio = excluded / max(total, 1)
        if ratio > 0.3:
            return "Low"
        if ratio > 0:
            return "Medium"
    return "High"


def render_response_contract(
    tool_name: str,
    result: dict[str, Any],
    board_caveats: list[str],
    insight_text: str,
) -> ChatResponse:
    answer, metrics, caveats = render_metrics(tool_name, result)
    all_caveats = board_caveats + caveats
    confidence = classify_confidence(tool_name, result, board_caveats)
    insight = (
        _extract_leadership_insight(insight_text)
        if tool_name == "generate_leadership_update"
        else _strip_duplicated_structure(insight_text)
    )
    return ChatResponse(
        answer=answer,
        metrics=metrics,
        insight=insight,
        caveats=all_caveats,
        confidence=confidence,
    )
