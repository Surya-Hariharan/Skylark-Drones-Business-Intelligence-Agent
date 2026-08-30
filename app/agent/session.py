import json
from typing import Any

from google.genai import types
from pydantic import BaseModel, ConfigDict

from app.kv_store import kv_available, kv_get, kv_set


class SessionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    history: list[Any] = []  # list[google.genai.types.Content], kept loosely typed to avoid a hard import here
    last_resolved_slots: dict[str, Any] = {}


_SESSIONS: dict[str, SessionState] = {}
_SESSION_TTL_SECONDS = 3600
_SESSION_KEY_PREFIX = "skylark:session:"


def _serialize(session: SessionState) -> str:
    return json.dumps(
        {
            "history": [c.model_dump(mode="json") for c in session.history],
            "last_resolved_slots": session.last_resolved_slots,
        }
    )


def _deserialize(raw: str) -> SessionState:
    parsed = json.loads(raw)
    history = [types.Content.model_validate(c) for c in parsed.get("history", [])]
    return SessionState(history=history, last_resolved_slots=parsed.get("last_resolved_slots", {}))


async def get_or_create_session(session_id: str) -> SessionState:
    """Backed by Vercel KV / Upstash Redis when configured, since a
    serverless function's process memory does not survive between
    invocations. Falls back to a module-level dict (correct only for a
    single long-lived process, e.g. local `uvicorn` dev) when it isn't.
    Callers must call `save_session` after mutating the returned state."""
    if kv_available():
        raw = await kv_get(_SESSION_KEY_PREFIX + session_id)
        if raw is not None:
            return _deserialize(raw)
        return SessionState()
    return _SESSIONS.setdefault(session_id, SessionState())


async def save_session(session_id: str, session: SessionState) -> None:
    if kv_available():
        await kv_set(_SESSION_KEY_PREFIX + session_id, _serialize(session), ex_seconds=_SESSION_TTL_SECONDS)
    else:
        _SESSIONS[session_id] = session


def merge_slots(previous: dict[str, Any], new_args: dict[str, Any]) -> dict[str, Any]:
    """Slot inheritance (system-prompt §10): a newly-resolved tool argument
    overwrites the prior value for that slot; slots absent from `new_args`
    (because the LLM inherited them, or they don't apply to this tool) are
    left untouched."""
    merged = dict(previous)
    for key, value in new_args.items():
        if value is not None:
            merged[key] = value
    return merged
