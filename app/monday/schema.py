from __future__ import annotations

from pydantic import BaseModel

from app.monday.client import FetchOutcome, MondayClient, MondayFetchError, MondayFetchResult

_SCHEMA_QUERY = """
query ($boardId: [ID!]) {
  boards(ids: $boardId) {
    id
    name
    columns {
      id
      title
      type
    }
  }
}
"""


class ColumnDef(BaseModel):
    id: str
    title: str
    type: str


class BoardSchema(BaseModel):
    board_id: str
    board_name: str
    columns: list[ColumnDef]


async def discover_schema(client: MondayClient, board_id: str) -> FetchOutcome[BoardSchema]:
    outcome = await client.fetch_raw(_SCHEMA_QUERY, {"boardId": [board_id]})
    if not outcome.ok:
        return outcome

    boards = outcome.data.get("boards") or []
    if not boards:
        return MondayFetchError(reason=f"Board {board_id} not found or inaccessible.", stage="graphql")

    board = boards[0]
    columns = [ColumnDef(id=c["id"], title=c["title"], type=c["type"]) for c in board.get("columns", [])]
    return MondayFetchResult(data=BoardSchema(board_id=board["id"], board_name=board["name"], columns=columns))
