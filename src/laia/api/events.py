"""REST endpoints for calendar events."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from laia.api.auth import require_api_key
from laia.db import get_session
from laia.schemas.events import EventCreate, EventList, EventRead, EventUpdate
from laia.services.calendar import CalendarService, EventNotFoundError

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    session: AsyncSession = Depends(get_session),
) -> EventRead:
    service = CalendarService(session)
    try:
        event = await service.create_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return EventRead.model_validate(event)


@router.get("", response_model=EventList)
async def search_events(
    q: str | None = Query(default=None, description="Search title, description, or location"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EventList:
    service = CalendarService(session)
    items, total = await service.search_events(query=q, start=start, end=end, limit=limit, offset=offset)
    return EventList(items=[EventRead.model_validate(item) for item in items], total=total)


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> EventRead:
    service = CalendarService(session)
    try:
        event = await service.get_event(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EventRead.model_validate(event)


@router.patch("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    session: AsyncSession = Depends(get_session),
) -> EventRead:
    service = CalendarService(session)
    try:
        event = await service.update_event(event_id, payload)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return EventRead.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    service = CalendarService(session)
    try:
        await service.delete_event(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
