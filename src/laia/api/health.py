"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from laia.api.auth import require_api_key
from laia.services.ollama import get_ollama_client

router = APIRouter(prefix="/api/health", tags=["health"], dependencies=[Depends(require_api_key)])


@router.get("/ollama")
async def ollama_health() -> dict:
    client = get_ollama_client()
    try:
        return await client.health()
    finally:
        await client.aclose()
