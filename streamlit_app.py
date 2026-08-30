"""Streamlit front end for the Skylark BI Agent.

Runs the agent in-process (imports app.agent.orchestrator.run_turn directly)
rather than going through the FastAPI HTTP layer, so there's no separate
server to start, no CORS config, and no network-layer failure mode between
the UI and the agent.
"""
import asyncio
import uuid

import streamlit as st

from app.agent.orchestrator import run_turn
from app.board_summary import build_board_summaries
from app.data_cache import get_cached_board_data

st.set_page_config(page_title="Skylark BI Agent", page_icon="📊", layout="centered")


def run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "log" not in st.session_state:
    st.session_state.log = []

with st.sidebar:
    st.header("Connected boards")
    try:
        board_data = run_async(get_cached_board_data())
        summaries = build_board_summaries(board_data)
        for summary in summaries:
            if summary.connected:
                st.success(f"{summary.name} — {summary.record_count} records")
                st.caption(f"Read as: **{summary.kind}**")
                for flag in summary.flags:
                    st.caption(f"⚠️ {flag}")
            else:
                st.error(f"{summary.name} — unusable: {summary.failure_reason}")

        st.divider()
        st.caption("**Available analysis**")
        if board_data.deals and board_data.work_orders:
            st.caption("All tools, including cross-board and leadership updates.")
        elif board_data.deals:
            st.caption("Pipeline and deal-side sector performance only — no Work Orders board.")
        elif board_data.work_orders:
            st.caption("Revenue and operations only — no Deals board.")
        else:
            st.caption("No usable business data connected.")
    except Exception as exc:
        st.error(f"Could not load board data: {exc}")

st.title("Skylark BI Agent")
st.caption("Ask about pipeline, revenue, operations, or sector performance from live Monday.com data.")

for entry in st.session_state.log:
    with st.chat_message(entry["role"]):
        if entry["kind"] == "structured":
            data = entry["data"]
            st.markdown(data.answer or "")
            if data.metrics:
                st.markdown("**Key metrics**")
                for m in data.metrics:
                    st.markdown(f"- {m}")
            if data.insight:
                st.markdown("**Insight**")
                st.markdown(data.insight)
            if data.caveats:
                st.markdown("**Data quality**")
                for c in data.caveats:
                    st.markdown(f"- {c}")
            if data.confidence:
                st.caption(f"Confidence: {data.confidence}")
        else:
            st.markdown(entry["text"])

if prompt := st.chat_input("e.g. What's our open pipeline in Energy?"):
    st.session_state.log.append({"role": "user", "kind": "text", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                turn = run_async(run_turn(st.session_state.session_id, prompt))
            except Exception as exc:
                turn = None
                st.error(f"An unexpected error occurred: {exc}")

        if turn is not None:
            if turn.kind == "structured" and turn.structured:
                data = turn.structured
                st.markdown(data.answer or "")
                if data.metrics:
                    st.markdown("**Key metrics**")
                    for m in data.metrics:
                        st.markdown(f"- {m}")
                if data.insight:
                    st.markdown("**Insight**")
                    st.markdown(data.insight)
                if data.caveats:
                    st.markdown("**Data quality**")
                    for c in data.caveats:
                        st.markdown(f"- {c}")
                if data.confidence:
                    st.caption(f"Confidence: {data.confidence}")
                st.session_state.log.append({"role": "assistant", "kind": "structured", "data": data})
            else:
                st.markdown(turn.text or "")
                st.session_state.log.append({"role": "assistant", "kind": "text", "text": turn.text or ""})
