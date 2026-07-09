"""Integration tests for calendar REST endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


def _event_payload(**overrides):
    data = {
        "title": "Dentist appointment",
        "description": "Six-month cleaning",
        "location": "123 Main St",
        "start_at": "2026-07-14T14:00:00-05:00",
        "end_at": "2026-07-14T15:00:00-05:00",
        "timezone": "America/Chicago",
        "all_day": False,
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_requires_api_key(client: AsyncClient) -> None:
    response = await client.get("/api/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_get_update_delete_event(client: AsyncClient, api_headers: dict) -> None:
    create = await client.post("/api/events", json=_event_payload(), headers=api_headers)
    assert create.status_code == 201
    body = create.json()
    event_id = body["id"]
    assert body["title"] == "Dentist appointment"
    assert body["all_day"] is False

    fetched = await client.get(f"/api/events/{event_id}", headers=api_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == event_id

    updated = await client.patch(
        f"/api/events/{event_id}",
        json={"title": "Dentist (rescheduled)", "location": "456 Oak Ave"},
        headers=api_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Dentist (rescheduled)"
    assert updated.json()["location"] == "456 Oak Ave"

    deleted = await client.delete(f"/api/events/{event_id}", headers=api_headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/events/{event_id}", headers=api_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_search_events(client: AsyncClient, api_headers: dict) -> None:
    await client.post("/api/events", json=_event_payload(title="Gym"), headers=api_headers)
    await client.post(
        "/api/events",
        json=_event_payload(
            title="Team standup",
            start_at="2026-07-15T09:00:00-05:00",
            end_at="2026-07-15T09:30:00-05:00",
        ),
        headers=api_headers,
    )

    by_title = await client.get("/api/events", params={"q": "gym"}, headers=api_headers)
    assert by_title.status_code == 200
    data = by_title.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Gym"

    by_range = await client.get(
        "/api/events",
        params={
            "start": "2026-07-15T00:00:00-05:00",
            "end": "2026-07-15T23:59:59-05:00",
        },
        headers=api_headers,
    )
    assert by_range.status_code == 200
    assert by_range.json()["total"] == 1
    assert by_range.json()["items"][0]["title"] == "Team standup"


@pytest.mark.asyncio
async def test_rejects_invalid_date_order(client: AsyncClient, api_headers: dict) -> None:
    response = await client.post(
        "/api/events",
        json=_event_payload(
            start_at="2026-07-14T15:00:00-05:00",
            end_at="2026-07-14T14:00:00-05:00",
        ),
        headers=api_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rejects_invalid_timezone(client: AsyncClient, api_headers: dict) -> None:
    response = await client.post(
        "/api/events",
        json=_event_payload(timezone="Not/AZone"),
        headers=api_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_all_day_event_normalized(client: AsyncClient, api_headers: dict) -> None:
    response = await client.post(
        "/api/events",
        json=_event_payload(
            title="Birthday",
            start_at="2026-08-01T12:00:00-05:00",
            end_at="2026-08-01T18:00:00-05:00",
            all_day=True,
        ),
        headers=api_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["all_day"] is True
    # Midnight America/Chicago on 2026-08-01 is 05:00 UTC (CDT).
    assert body["start_at"] in {"2026-08-01T05:00:00Z", "2026-08-01T00:00:00-05:00"}
    assert body["end_at"] in {"2026-08-02T05:00:00Z", "2026-08-02T00:00:00-05:00"}


@pytest.mark.asyncio
async def test_get_missing_event(client: AsyncClient, api_headers: dict) -> None:
    response = await client.get(f"/api/events/{uuid.uuid4()}", headers=api_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
