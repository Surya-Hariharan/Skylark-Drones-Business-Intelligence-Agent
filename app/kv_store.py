"""Thin async client for Vercel KV / Upstash Redis's REST API.

Used to move the board-data cache and session store out of module-level
memory, which does not survive between invocations of a serverless Python
function (see DECISION_LOG.md). Every call is a no-op
returning None when KV_REST_API_URL / KV_REST_API_TOKEN aren't set, so local
`uvicorn` dev keeps working without provisioning a KV instance (callers fall
back to an in-memory dict in that case).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_KV_URL = os.environ.get("KV_REST_API_URL")
_KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")


def kv_available() -> bool:
    return bool(_KV_URL and _KV_TOKEN)


async def _command(*parts: Any) -> Any:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            _KV_URL, headers={"Authorization": f"Bearer {_KV_TOKEN}"}, json=list(parts)
        )
    response.raise_for_status()
    return response.json().get("result")


async def kv_get(key: str) -> str | None:
    if not kv_available():
        return None
    return await _command("GET", key)


async def kv_set(key: str, value: str, ex_seconds: int | None = None) -> None:
    if not kv_available():
        return
    if ex_seconds:
        await _command("SET", key, value, "EX", ex_seconds)
    else:
        await _command("SET", key, value)
