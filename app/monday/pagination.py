from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.monday.client import FetchOutcome, MondayClient, MondayFetchError, MondayFetchResult

_FIRST_PAGE_QUERY = """
query ($boardId: [ID!], $limit: Int!) {
  boards(ids: $boardId) {
    items_page(limit: $limit) {
      cursor
      items {
        id
        name
        column_values {
          id
          text
          value
        }
      }
    }
  }
}
"""

_NEXT_PAGE_QUERY = """
query ($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      column_values {
        id
        text
        value
      }
    }
  }
}
"""

_PAGE_SIZE = 100


class RawItem(BaseModel):
    id: str
    name: str
    column_values: dict[str, Any]  # keyed by column id -> {"text": ..., "value": ...}


def _parse_items(raw_items: list[dict]) -> list[RawItem]:
    parsed = []
    for item in raw_items:
        column_values = {
            cv["id"]: {"text": cv.get("text"), "value": cv.get("value")} for cv in item.get("column_values", [])
        }
        parsed.append(RawItem(id=item["id"], name=item["name"], column_values=column_values))
    return parsed


async def fetch_all_items(client: MondayClient, board_id: str) -> FetchOutcome[list[RawItem]]:
    """Loops on Monday's items_page/next_items_page cursor until no cursor is
    returned. Must not stop after the first page — boards here have more rows
    than a single default page size."""
    outcome = await client.fetch_raw(_FIRST_PAGE_QUERY, {"boardId": [board_id], "limit": _PAGE_SIZE})
    if not outcome.ok:
        return outcome

    boards = outcome.data.get("boards") or []
    if not boards:
        return MondayFetchError(reason=f"Board {board_id} not found or inaccessible.", stage="graphql")

    items_page = boards[0]["items_page"]
    all_items = _parse_items(items_page["items"])
    cursor = items_page.get("cursor")

    while cursor:
        outcome = await client.fetch_raw(_NEXT_PAGE_QUERY, {"cursor": cursor, "limit": _PAGE_SIZE})
        if not outcome.ok:
            return outcome
        next_page = outcome.data["next_items_page"]
        all_items.extend(_parse_items(next_page["items"]))
        cursor = next_page.get("cursor")

    return MondayFetchResult(data=all_items)
