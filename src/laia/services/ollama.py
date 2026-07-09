"""Ollama HTTP client with structured JSON Schema output."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from laia.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaError(Exception):
    """Raised when an Ollama request fails."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
            models = [m.get("name") for m in payload.get("models", [])]
            return {
                "ok": True,
                "base_url": self.base_url,
                "configured_model": self.model,
                "models": models,
            }
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "base_url": self.base_url,
                "configured_model": self.model,
                "error": str(exc),
            }

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """Call Ollama chat with JSON Schema constrained output and validate with Pydantic."""
        json_schema = schema.model_json_schema()
        payload = {
            "model": model or self.model,
            "stream": False,
            "format": json_schema,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise OllamaError("Ollama returned empty content")
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            logger.warning("Ollama structured output failed validation: %s", content)
            raise OllamaError(f"Invalid structured output: {exc}") from exc


def get_ollama_client(settings: Settings | None = None) -> OllamaClient:
    settings = settings or get_settings()
    return OllamaClient(base_url=settings.ollama_base_url, model=settings.ollama_model)
