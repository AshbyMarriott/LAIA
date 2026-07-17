"""Assistant chat API integration with mocked orchestrator path via dependency override is heavy;
this smoke-tests auth and request validation on the chat endpoint.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_requires_api_key(client: AsyncClient) -> None:
    response = await client.post("/api/assistant/chat", json={"message": "hi"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(client: AsyncClient, api_headers: dict) -> None:
    response = await client.post(
        "/api/assistant/chat",
        json={"message": ""},
        headers=api_headers,
    )
    assert response.status_code == 422
