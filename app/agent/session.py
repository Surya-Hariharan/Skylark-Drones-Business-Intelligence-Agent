from typing import Any

from pydantic import BaseModel, ConfigDict


class SessionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    history: list[Any] = []  # list[google.genai.types.Content], kept loosely typed to avoid a hard import here
    last_resolved_slots: dict[str, Any] = {}


_SESSIONS: dict[str, SessionState] = {}


async def get_or_create_session(session_id: str) -> SessionState:
    """Held in a module-level dict, which is correct because Streamlit runs
    as a single long-lived process. Callers must call `save_session` after
    mutating the returned state."""
    return _SESSIONS.setdefault(session_id, SessionState())


async def save_session(session_id: str, session: SessionState) -> None:
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
