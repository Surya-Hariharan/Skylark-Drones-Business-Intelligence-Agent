from typing import Literal

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.agent.formatting import ChatResponse, render_response_contract
from app.agent.session import SessionState, get_or_create_session, merge_slots, save_session
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tools import build_tool_declarations, dispatch_tool
from app.config import settings
from app.data_cache import get_cached_board_data

_client = genai.Client(api_key=settings.gemini_api_key)


class ChatTurnResult(BaseModel):
    kind: Literal["structured", "text"]
    structured: ChatResponse | None = None
    text: str | None = None


def _build_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=build_tool_declarations(),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode=types.FunctionCallingConfigMode.AUTO)
        ),
    )


async def run_turn(session_id: str, user_message: str) -> ChatTurnResult:
    session = await get_or_create_session(session_id)
    try:
        return await _run_turn(session, user_message)
    finally:
        # Persisted unconditionally so every exit path (including a mid-loop
        # tool call or an early LLM-error return) keeps the session's
        # mutations — process memory doesn't survive between invocations of
        # a serverless function, so nothing is durable until this runs.
        await save_session(session_id, session)


async def _run_turn(session: SessionState, user_message: str) -> ChatTurnResult:
    board_data = await get_cached_board_data()

    context_parts = []
    if session.last_resolved_slots:
        slots_note = ", ".join(f"{k}={v}" for k, v in session.last_resolved_slots.items() if v is not None)
        if slots_note:
            context_parts.append(
                types.Part.from_text(
                    text=f"[Context from the previous turn — inherit any of these the current message "
                    f"doesn't override or contradict: {slots_note}]"
                )
            )
    context_parts.append(types.Part.from_text(text=user_message))

    contents = list(session.history) + [types.Content(role="user", parts=context_parts)]
    config = _build_config()

    last_tool_name: str | None = None
    last_dispatch = None

    for _ in range(settings.max_tool_hops):
        try:
            response = await _client.aio.models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
        except genai_errors.APIError as exc:
            return ChatTurnResult(
                kind="text",
                text=f"I couldn't reach the language model provider right now, so I can't process this "
                f"request: {exc}",
            )
        except Exception as exc:  # network-layer failures etc. — never let this surface as a raw 500
            return ChatTurnResult(
                kind="text",
                text=f"An unexpected error occurred while processing this request: {exc}",
            )
        candidate = response.candidates[0]
        contents.append(candidate.content)

        calls = response.function_calls or []
        if not calls:
            session.history = contents
            final_text = response.text or ""
            if last_dispatch is not None and last_dispatch.ok:
                structured = render_response_contract(
                    last_tool_name, last_dispatch.result, last_dispatch.board_caveats, final_text
                )
                return ChatTurnResult(kind="structured", structured=structured)
            return ChatTurnResult(kind="text", text=final_text)

        response_parts = []
        for call in calls:
            args = dict(call.args or {})
            outcome = dispatch_tool(call.name, args, board_data)
            session.last_resolved_slots = merge_slots(session.last_resolved_slots, args)
            last_tool_name, last_dispatch = call.name, outcome
            response_parts.append(types.Part.from_function_response(name=call.name, response=outcome.model_dump(mode="json")))

        contents.append(types.Content(role="user", parts=response_parts))

    session.history = contents
    return ChatTurnResult(
        kind="text",
        text="I wasn't able to resolve this after several attempts — could you rephrase or narrow the question?",
    )
