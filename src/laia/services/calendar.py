"""Calendar service — single source of truth for event CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from laia.models.event import Event
from laia.schemas.events import EventCreate, EventUpdate


class EventNotFoundError(Exception):
    def __init__(self, event_id: uuid.UUID) -> None:
        self.event_id = event_id
        super().__init__(f"Event not found: {event_id}")


class CalendarService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(self, data: EventCreate) -> Event:
        start_at, end_at = self._normalize_bounds(
            start_at=data.start_at,
            end_at=data.end_at,
            timezone=data.timezone,
            all_day=data.all_day,
        )
        event = Event(
            title=data.title.strip(),
            description=data.description,
            location=data.location,
            start_at=start_at,
            end_at=end_at,
            timezone=data.timezone,
            all_day=data.all_day,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def get_event(self, event_id: uuid.UUID) -> Event:
        event = await self._session.get(Event, event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        return event

    async def search_events(
        self,
        *,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Event.title.ilike(pattern),
                    Event.description.ilike(pattern),
                    Event.location.ilike(pattern),
                )
            )
        if start is not None:
            filters.append(Event.end_at >= start)
        if end is not None:
            filters.append(Event.start_at <= end)

        where = and_(*filters) if filters else None
        count_stmt: Select[tuple[int]] = select(func.count()).select_from(Event)
        list_stmt: Select[tuple[Event]] = (
            select(Event).order_by(Event.start_at.asc()).limit(limit).offset(offset)
        )
        if where is not None:
            count_stmt = count_stmt.where(where)
            list_stmt = list_stmt.where(where)

        total = int((await self._session.execute(count_stmt)).scalar_one())
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return list(rows), total

    async def update_event(self, event_id: uuid.UUID, data: EventUpdate) -> Event:
        event = await self.get_event(event_id)
        payload = data.model_dump(exclude_unset=True)

        if "title" in payload and payload["title"] is not None:
            event.title = payload["title"].strip()
        if "description" in payload:
            event.description = payload["description"]
        if "location" in payload:
            event.location = payload["location"]
        if "timezone" in payload and payload["timezone"] is not None:
            event.timezone = payload["timezone"]
        if "all_day" in payload and payload["all_day"] is not None:
            event.all_day = payload["all_day"]

        start_at = payload.get("start_at", event.start_at)
        end_at = payload.get("end_at", event.end_at)
        if end_at <= start_at:
            raise ValueError("end_at must be greater than start_at")

        start_at, end_at = self._normalize_bounds(
            start_at=start_at,
            end_at=end_at,
            timezone=event.timezone,
            all_day=event.all_day,
        )
        event.start_at = start_at
        event.end_at = end_at
        event.updated_at = datetime.now(tz=ZoneInfo("UTC"))

        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def delete_event(self, event_id: uuid.UUID) -> None:
        event = await self.get_event(event_id)
        await self._session.delete(event)
        await self._session.flush()

    @staticmethod
    def _normalize_bounds(
        *,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        all_day: bool,
    ) -> tuple[datetime, datetime]:
        tz = ZoneInfo(timezone)
        if not all_day:
            if start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=tz)
            if end_at.tzinfo is None:
                end_at = end_at.replace(tzinfo=tz)
            return start_at, end_at

        local_start = start_at.astimezone(tz) if start_at.tzinfo else start_at.replace(tzinfo=tz)
        local_end = end_at.astimezone(tz) if end_at.tzinfo else end_at.replace(tzinfo=tz)
        day_start = datetime.combine(local_start.date(), time.min, tzinfo=tz)
        # Exclusive next-midnight end: if already midnight after start, keep it (resolve_event_bounds
        # and some clients pass an exclusive boundary). Otherwise treat end's calendar day as
        # inclusive and advance to the following midnight.
        if local_end.time() == time.min and local_end > day_start:
            day_end = local_end
        else:
            day_end = datetime.combine(local_end.date() + timedelta(days=1), time.min, tzinfo=tz)
        if day_end <= day_start:
            day_end = day_start + timedelta(days=1)
        return day_start, day_end
