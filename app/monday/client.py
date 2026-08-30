from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, Union

import httpx
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T")


class MondayFetchError(BaseModel):
    ok: Literal[False] = False
    reason: str
    stage: Literal["auth", "network", "graphql", "timeout", "parse"]


class MondayFetchResult(BaseModel, Generic[T]):
    ok: Literal[True] = True
    data: T


FetchOutcome = Union[MondayFetchResult[T], MondayFetchError]


class MondayClient:
    def __init__(self, token: str | None = None, timeout_s: float | None = None):
        self.token = token or settings.monday_api_token
        self.timeout_s = timeout_s or settings.monday_timeout_s

    async def fetch_raw(self, query: str, variables: dict[str, Any] | None = None) -> FetchOutcome[dict]:
        """POST a GraphQL query to Monday. Never raises — every failure mode
        (auth, network, timeout, malformed response, GraphQL-level errors)
        is caught and returned as a typed MondayFetchError instead."""
        headers = {"Authorization": self.token, "Content-Type": "application/json"}
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(settings.monday_api_url, json=payload, headers=headers)
        except httpx.TimeoutException:
            return MondayFetchError(reason="Request to Monday.com timed out.", stage="timeout")
        except httpx.RequestError as exc:
            return MondayFetchError(reason=f"Network error contacting Monday.com: {exc}", stage="network")

        if response.status_code == 401:
            return MondayFetchError(reason="Monday.com rejected the API token (401 Unauthorized).", stage="auth")
        if response.status_code >= 400:
            return MondayFetchError(
                reason=f"Monday.com returned HTTP {response.status_code}: {response.text[:300]}",
                stage="network",
            )

        try:
            body = response.json()
        except ValueError:
            return MondayFetchError(reason="Monday.com response was not valid JSON.", stage="parse")

        if "errors" in body and body["errors"]:
            return MondayFetchError(
                reason=f"Monday.com GraphQL error: {body['errors']}",
                stage="graphql",
            )

        if "data" not in body:
            return MondayFetchError(reason="Monday.com response missing 'data' field.", stage="parse")

        return MondayFetchResult(data=body["data"])
