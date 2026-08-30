from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.orchestrator import run_turn

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatApiResponse(BaseModel):
    kind: str
    answer: str | None = None
    metrics: list[str] | None = None
    insight: str | None = None
    caveats: list[str] | None = None
    confidence: str | None = None
    text: str | None = None


@router.post("/api/chat", response_model=ChatApiResponse)
async def chat(request: ChatRequest) -> ChatApiResponse:
    turn = await run_turn(request.session_id, request.message)
    if turn.kind == "structured" and turn.structured:
        s = turn.structured
        return ChatApiResponse(
            kind="structured",
            answer=s.answer,
            metrics=s.metrics,
            insight=s.insight,
            caveats=s.caveats,
            confidence=s.confidence,
        )
    return ChatApiResponse(kind="text", text=turn.text)
