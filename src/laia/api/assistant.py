"""Assistant chat endpoint."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from laia.api.auth import require_api_key
from laia.db import get_session
from laia.orchestrator.pipeline import Orchestrator
from laia.schemas.assistant import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/assistant",
    tags=["assistant"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    started = time.perf_counter()
    orchestrator = Orchestrator(session)
    response = await orchestrator.handle(
        message=payload.message,
        conversation_id=payload.conversation_id,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    command = response.action.command if response.action else (
        response.pending.command if response.pending else None
    )
    outcome = "action" if response.action else ("pending" if response.pending else "no_action")
    logger.info(
        "assistant_chat command=%s outcome=%s latency_ms=%s conversation_id=%s",
        command,
        outcome,
        latency_ms,
        response.conversation_id,
    )
    return response
