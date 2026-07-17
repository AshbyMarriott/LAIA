"""Ollama client unit tests with httpx mock transport."""

from __future__ import annotations

import json

import httpx
import pytest

from laia.schemas.assistant import ClassificationResult, CommandName
from laia.services.ollama import OllamaClient, OllamaError


@pytest.mark.asyncio
async def test_structured_output_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert "format" in body
        assert body.get("think") is False
        assert body.get("options", {}).get("num_predict") == 512
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"command": "create_event"})}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ollama:11434") as client:
        ollama = OllamaClient(client=client, base_url="http://ollama:11434", model="qwen2.5:7b")
        result = await ollama.structured(
            system="sys",
            user="create dentist",
            schema=ClassificationResult,
        )
    assert result.command == CommandName.CREATE_EVENT


@pytest.mark.asyncio
async def test_structured_output_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "{}"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ollama:11434") as client:
        ollama = OllamaClient(client=client, base_url="http://ollama:11434", model="qwen2.5:7b")
        with pytest.raises(OllamaError):
            await ollama.structured(system="sys", user="x", schema=ClassificationResult)


@pytest.mark.asyncio
async def test_health_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ollama:11434") as client:
        ollama = OllamaClient(client=client, base_url="http://ollama:11434", model="qwen2.5:7b")
        health = await ollama.health()
    assert health["ok"] is True
    assert "qwen2.5:7b" in health["models"]
