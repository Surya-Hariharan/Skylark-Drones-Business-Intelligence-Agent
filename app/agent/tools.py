from typing import Any

from google.genai import types
from pydantic import BaseModel

from app.bi.common import WorkOrderFilters
from app.bi.cross_board import analyze_cross_board
from app.bi.leadership import generate_leadership_update
from app.bi.operations import analyze_operations
from app.bi.pipeline import PipelineFilters, analyze_pipeline
from app.bi.revenue import RevenueBasis, analyze_revenue
from app.bi.sectors import analyze_sector_performance
from app.data_cache import BoardCacheEntry

# Exactly one tool per BI function (system-prompt §28: minimum tools, not
# 8+ micro-tools).

_NULLABLE_STRING = {"type": "string", "nullable": True}
_NULLABLE_DATE = {"type": "string", "format": "date", "nullable": True, "description": "ISO date YYYY-MM-DD"}

_PIPELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "sector": _NULLABLE_STRING,
        "stage": _NULLABLE_STRING,
        "time_from": _NULLABLE_DATE,
        "time_to": _NULLABLE_DATE,
    },
}

_REVENUE_SCHEMA = {
    "type": "object",
    "properties": {
        "sector": _NULLABLE_STRING,
        "time_from": _NULLABLE_DATE,
        "time_to": _NULLABLE_DATE,
        "requested_basis": {
            "type": "string",
            "enum": [b.value for b in RevenueBasis],
            "nullable": True,
            "description": "Which financial concept to report. Infer from user phrasing "
            "('billed'/'invoice' -> billed_value_incl_gst, 'receivable'/'outstanding' -> "
            "receivable, 'contract value'/'excl gst' -> contract_value_excl_gst). "
            "Omit if the phrasing gives no signal — the tool defaults conservatively.",
        },
    },
}

_OPERATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "sector": _NULLABLE_STRING,
        "status": _NULLABLE_STRING,
        "time_from": _NULLABLE_DATE,
        "time_to": _NULLABLE_DATE,
    },
}

_SECTOR_SCHEMA = {
    "type": "object",
    "properties": {"sector": _NULLABLE_STRING},
}

_CROSS_BOARD_SCHEMA = {"type": "object", "properties": {}}

_LEADERSHIP_SCHEMA = {"type": "object", "properties": {}}


def build_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="analyze_pipeline",
                    description="Deal pipeline: open deal count/value, breakdown by stage and by "
                    "closure-probability (High/Medium/Low, reported as-is, never numerically weighted).",
                    parameters_json_schema=_PIPELINE_SCHEMA,
                ),
                types.FunctionDeclaration(
                    name="analyze_revenue",
                    description="Financial totals from Work Orders: contract value (excl. GST), billed "
                    "value (incl. GST), or receivable — always one explicit basis, never a bare 'revenue' figure.",
                    parameters_json_schema=_REVENUE_SCHEMA,
                ),
                types.FunctionDeclaration(
                    name="analyze_operations",
                    description="Operational metrics from Work Orders: execution status distribution, "
                    "billing status distribution, AR-priority count.",
                    parameters_json_schema=_OPERATIONS_SCHEMA,
                ),
                types.FunctionDeclaration(
                    name="analyze_sector_performance",
                    description="Combined pipeline + work-order summary for one sector, or overall if no "
                    "sector is given.",
                    parameters_json_schema=_SECTOR_SCHEMA,
                ),
                types.FunctionDeclaration(
                    name="analyze_cross_board",
                    description="Compares Deals and Work Orders across all sectors (e.g. strong pipeline "
                    "vs weak execution) — also the tool to use for 'pipeline (or work orders) broken down "
                    "by sector', since it returns one row per sector rather than a single scoped total. "
                    "Sector-level only — deals and work orders cannot be reliably matched individually.",
                    parameters_json_schema=_CROSS_BOARD_SCHEMA,
                ),
                types.FunctionDeclaration(
                    name="generate_leadership_update",
                    description="Full leadership update: pipeline, operations, financial, sector "
                    "highlights, and risks, composed from the other tools.",
                    parameters_json_schema=_LEADERSHIP_SCHEMA,
                ),
            ]
        )
    ]


class ToolDispatchOutcome(BaseModel):
    """What dispatch_tool returns to the orchestrator: either a structured BI
    result plus quality caveats to render, or an explanation of why no
    result was produced (technical failure / no board data available)."""

    ok: bool
    result: dict[str, Any] | None = None
    board_caveats: list[str] = []
    error: str | None = None


def _iso_to_date(value: str | None):
    if not value:
        return None
    from datetime import date

    return date.fromisoformat(value)


def _board_failure_caveats(board_data: BoardCacheEntry) -> list[str]:
    caveats = []
    if board_data.deal_failure:
        caveats.append(f"Could not retrieve Deals data: {board_data.deal_failure.reason}")
    if board_data.wo_failure:
        caveats.append(f"Could not retrieve Work Orders data: {board_data.wo_failure.reason}")
    return caveats


def dispatch_tool(name: str, args: dict[str, Any], board_data: BoardCacheEntry) -> ToolDispatchOutcome:
    """The single place implementing the 3-way error branch (system-prompt
    §22): if the board this tool needs failed to fetch, return a technical
    failure explanation rather than a guessed/partial result; otherwise run
    the deterministic BI function and pass its structured result (with any
    data-quality caveats already embedded) straight through."""
    board_caveats = _board_failure_caveats(board_data)

    needs_deals = name in ("analyze_pipeline", "analyze_sector_performance", "analyze_cross_board", "generate_leadership_update")
    needs_wo = name in ("analyze_revenue", "analyze_operations", "analyze_sector_performance", "analyze_cross_board", "generate_leadership_update")

    if needs_deals and board_data.deal_failure and not board_data.deals:
        return ToolDispatchOutcome(
            ok=False, error=f"Deals data could not be retrieved: {board_data.deal_failure.reason}", board_caveats=board_caveats
        )
    if needs_wo and board_data.wo_failure and not board_data.work_orders:
        return ToolDispatchOutcome(
            ok=False,
            error=f"Work Orders data could not be retrieved: {board_data.wo_failure.reason}",
            board_caveats=board_caveats,
        )

    if name == "analyze_pipeline":
        filters = PipelineFilters(
            sector=args.get("sector"),
            stage=args.get("stage"),
            time_from=_iso_to_date(args.get("time_from")),
            time_to=_iso_to_date(args.get("time_to")),
        )
        result = analyze_pipeline(board_data.deals, filters)
    elif name == "analyze_revenue":
        filters = WorkOrderFilters(
            sector=args.get("sector"),
            time_from=_iso_to_date(args.get("time_from")),
            time_to=_iso_to_date(args.get("time_to")),
        )
        basis = RevenueBasis(args["requested_basis"]) if args.get("requested_basis") else None
        result = analyze_revenue(board_data.work_orders, filters, basis)
    elif name == "analyze_operations":
        filters = WorkOrderFilters(
            sector=args.get("sector"),
            status=args.get("status"),
            time_from=_iso_to_date(args.get("time_from")),
            time_to=_iso_to_date(args.get("time_to")),
        )
        result = analyze_operations(board_data.work_orders, filters)
    elif name == "analyze_sector_performance":
        result = analyze_sector_performance(board_data.deals, board_data.work_orders, args.get("sector"))
    elif name == "analyze_cross_board":
        result = analyze_cross_board(board_data.deals, board_data.work_orders)
    elif name == "generate_leadership_update":
        result = generate_leadership_update(board_data.deals, board_data.work_orders)
    else:
        return ToolDispatchOutcome(ok=False, error=f"Unknown tool '{name}'.", board_caveats=board_caveats)

    return ToolDispatchOutcome(ok=True, result=result.model_dump(mode="json"), board_caveats=board_caveats)
