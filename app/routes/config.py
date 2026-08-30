from fastapi import APIRouter
from pydantic import BaseModel

from app.board_summary import BoardSummary, build_board_summaries
from app.data_cache import get_cached_board_data

router = APIRouter()


class BoardsConfigResponse(BaseModel):
    boards: list[BoardSummary]


@router.get("/api/config/boards", response_model=BoardsConfigResponse)
async def get_boards_config() -> BoardsConfigResponse:
    board_data = await get_cached_board_data()
    return BoardsConfigResponse(boards=build_board_summaries(board_data))
