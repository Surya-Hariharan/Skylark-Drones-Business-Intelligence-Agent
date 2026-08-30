from app.agent.formatting import render_response_contract

_PIPELINE_RESULT = {
    "total_open_deals": 7,
    "total_open_value": 25569056.0,
    "by_stage": {"E. Proposal/Commercials Sent": 2},
    "by_close_confidence": {"High": 3, "Medium": 0, "Low": 3},
    "unclassified_confidence_count": 1,
    "excluded_count": 0,
    "caveats": [],
}

_LEADERSHIP_RESULT = {
    "pipeline": {"total_open_deals": 41, "total_open_value": 357870995.0},
    "operations": {"total_work_orders": 176},
    "financial": {"basis_label": "Contract value (excl. GST)", "total": 211649409.0},
    "sector_highlights": [{"sector": "Tender", "open_pipeline_value": 226114562.0}],
    "risks_and_attention": [],
    "caveats": [],
}


def test_markdown_duplicated_structure_is_stripped():
    insight_text = (
        "I can't break it down further.\n\n"
        "### Answer\nOpen pipeline is ₹25.5M.\n\n"
        "### Key metrics\n* Open deals: 7\n\n"
        "### Data quality\n* 1 deal unclassified."
    )
    response = render_response_contract("analyze_pipeline", _PIPELINE_RESULT, [], insight_text)
    assert response.insight == "I can't break it down further."


def test_plain_text_duplicated_structure_is_stripped():
    # Observed live: gemini-2.5-flash sometimes duplicates structure using
    # plain "Label:" lines instead of markdown headers.
    insight_text = (
        "Answer:\n"
        "This year's billed value is ₹838,527.\n\n"
        "Key metrics:\n"
        "* Billed value: ₹838,527\n\n"
        "Insight:\n"
        "Collection efficiency looks healthy.\n\n"
        "Data quality:\n"
        "No issues detected."
    )
    response = render_response_contract("analyze_pipeline", _PIPELINE_RESULT, [], insight_text)
    assert response.insight == "See the metrics above for the full breakdown."


def test_plain_text_duplicate_with_leading_prose_keeps_the_prose():
    insight_text = (
        "Collections are tracking well against billed value this year.\n\n"
        "Key metrics:\n* Billed value: ₹838,527"
    )
    response = render_response_contract("analyze_pipeline", _PIPELINE_RESULT, [], insight_text)
    assert response.insight == "Collections are tracking well against billed value this year."


def test_leadership_insight_keeps_only_executive_summary_and_key_takeaway():
    insight_text = (
        "## Executive Summary\n\nPipeline is healthy at ₹357M.\n\n"
        "## Pipeline\n\nOpen deals: 41.\n\n"
        "## Operations\n\n176 work orders.\n\n"
        "## Key Takeaway\n\nFocus on Renewables next quarter."
    )
    response = render_response_contract("generate_leadership_update", _LEADERSHIP_RESULT, [], insight_text)
    assert "Pipeline is healthy at ₹357M." in response.insight
    assert "Focus on Renewables next quarter." in response.insight
    assert "Open deals: 41" not in response.insight
    assert "176 work orders" not in response.insight


def test_leadership_insight_handles_plain_text_labels_too():
    insight_text = (
        "Executive Summary:\n"
        "Pipeline is healthy at ₹357M.\n\n"
        "Pipeline:\n"
        "Open deals: 41.\n\n"
        "Key Takeaway:\n"
        "Focus on Renewables next quarter."
    )
    response = render_response_contract("generate_leadership_update", _LEADERSHIP_RESULT, [], insight_text)
    assert "Pipeline is healthy at ₹357M." in response.insight
    assert "Focus on Renewables next quarter." in response.insight
    assert "Open deals: 41" not in response.insight


def test_plain_insight_with_no_headers_passes_through_unchanged():
    insight_text = "Our pipeline is concentrated in later stages, which is a healthy sign."
    response = render_response_contract("analyze_pipeline", _PIPELINE_RESULT, [], insight_text)
    assert response.insight == insight_text


def test_leadership_confidence_inherits_worst_constituent():
    """The leadership update is a composition of the other results, so it
    must not report High while one of its parts is degraded — it has no
    denominator of its own and previously always fell through to High."""
    result = {
        **_LEADERSHIP_RESULT,
        # 20 of 41 open deals excluded -> the pipeline part alone is Low.
        "pipeline": {"total_open_deals": 41, "total_open_value": 1.0, "excluded_count": 20},
    }

    rendered = render_response_contract("generate_leadership_update", result, [], "prose")

    assert rendered.confidence == "Low"


def test_leadership_confidence_high_only_when_every_part_is_clean():
    rendered = render_response_contract("generate_leadership_update", _LEADERSHIP_RESULT, [], "prose")
    assert rendered.confidence == "High"


def test_sector_performance_confidence_reflects_its_caveats():
    clean = {"sector": "Mining", "deal_count": 3, "open_pipeline_value": 1.0,
             "work_order_count": 2, "revenue_total": 5.0,
             "revenue_basis_label": "Contract value (excl. GST)", "caveats": []}
    degraded = {**clean, "caveats": ["2 of 3 open deals in this scope have no usable value."]}

    assert render_response_contract("analyze_sector_performance", clean, [], "p").confidence == "High"
    assert render_response_contract("analyze_sector_performance", degraded, [], "p").confidence == "Medium"


def test_board_level_caveat_forces_low_confidence_everywhere():
    rendered = render_response_contract(
        "generate_leadership_update", _LEADERSHIP_RESULT, ["Could not retrieve Deals data"], "prose"
    )
    assert rendered.confidence == "Low"
