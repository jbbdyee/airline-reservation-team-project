from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

from app.schemas.dy.event_schema import EventLogFilter
from app.services.dy.event_service import (
    EventLogNotFoundError,
    fetch_events_after,
    get_event_log,
    get_latest_event_id,
    list_event_logs,
    stream_event_logs,
)


FLIGHT_ID = UUID("00000000-0000-0000-0000-00000000c001")
BOOKING_ID = UUID("00000000-0000-0000-0000-00000000e001")


def event_row(event_id: int = 1, **overrides: Any) -> dict[str, Any]:
    row = {
        "id": event_id,
        "event_type": "BOOKING_CHANGED",
        "resource_id": str(BOOKING_ID),
        "flight_id": str(FLIGHT_ID),
        "booking_id": str(BOOKING_ID),
        "actor_user_id": "00000000-0000-0000-0000-00000000b002",
        "payload": {"action": "CREATED", "status": "CONFIRMED"},
        "created_at": "2026-08-07T03:00:00",
    }
    row.update(overrides)
    return row


@dataclass
class FakeResponse:
    data: Any
    count: int | None = None


class FakeQuery:
    def __init__(self, response: FakeResponse, calls: list) -> None:
        self.response = response
        self.calls = calls

    def _chain(self, method: str, value: Any = None):
        self.calls.append((method, value))
        return self

    def select(self, value, **kwargs): return self._chain("select", (value, kwargs))
    def eq(self, column, value): return self._chain("eq", (column, value))
    def gt(self, column, value): return self._chain("gt", (column, value))
    def gte(self, column, value): return self._chain("gte", (column, value))
    def lte(self, column, value): return self._chain("lte", (column, value))
    def order(self, column, **kwargs): return self._chain("order", (column, kwargs))
    def range(self, start, end): return self._chain("range", (start, end))
    def limit(self, value): return self._chain("limit", value)
    def execute(self): return self.response


class FakeSupabase:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Any]] = []

    def table(self, name: str) -> FakeQuery:
        assert name == "event_logs"
        if not self.responses:
            raise AssertionError("event_logs 가짜 응답이 부족합니다.")
        return FakeQuery(self.responses.pop(0), self.calls)


def test_list_event_logs_applies_combined_filters_and_page() -> None:
    fake = FakeSupabase([FakeResponse([event_row()], count=25)])
    filters = EventLogFilter(
        event_type="BOOKING_CHANGED",
        flight_id=FLIGHT_ID,
        booking_id=BOOKING_ID,
        start_at="2026-08-07T00:00:00+09:00",
        end_at="2026-08-08T00:00:00+09:00",
        page=2,
        page_size=10,
    )

    result = list_event_logs(fake, filters)  # type: ignore[arg-type]

    assert result.total == 25
    assert result.total_pages == 3
    assert ("eq", ("event_type", "BOOKING_CHANGED")) in fake.calls
    assert ("eq", ("flight_id", str(FLIGHT_ID))) in fake.calls
    assert ("gte", ("created_at", "2026-08-06T15:00:00")) in fake.calls
    assert ("range", (10, 19)) in fake.calls


def test_get_event_log_returns_detail_or_404() -> None:
    found = FakeSupabase([FakeResponse([event_row()])])
    missing = FakeSupabase([FakeResponse([])])

    assert get_event_log(found, 1).payload["status"] == "CONFIRMED"  # type: ignore[arg-type]
    with pytest.raises(EventLogNotFoundError):
        get_event_log(missing, 999)  # type: ignore[arg-type]


def test_latest_cursor_and_fetch_after() -> None:
    latest = FakeSupabase([FakeResponse([{"id": 12}])])
    events = FakeSupabase([FakeResponse([event_row(13)])])

    assert get_latest_event_id(latest) == 12  # type: ignore[arg-type]
    result = fetch_events_after(events, 12, FLIGHT_ID)  # type: ignore[arg-type]

    assert result[0].id == 13
    assert ("gt", ("id", 12)) in events.calls
    assert ("eq", ("flight_id", str(FLIGHT_ID))) in events.calls


def test_sse_stream_formats_id_event_and_json_data() -> None:
    fake = FakeSupabase([FakeResponse([event_row(13)])])

    async def read_one() -> str:
        generator = stream_event_logs(
            fake,  # type: ignore[arg-type]
            last_event_id=12,
            poll_interval=0,
        )
        frame = await anext(generator)
        await generator.aclose()
        return frame

    frame = asyncio.run(read_one())

    assert frame.startswith("id: 13\nevent: booking_changed\ndata: ")
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["id"] == 13
    assert payload["created_at"] == "2026-08-07T03:00:00Z"


def test_sse_stream_sends_heartbeat_and_stops_on_disconnect() -> None:
    fake = FakeSupabase([FakeResponse([])])

    async def read_heartbeat() -> str:
        generator = stream_event_logs(
            fake,  # type: ignore[arg-type]
            last_event_id=0,
            poll_interval=0,
            heartbeat_interval=0,
        )
        frame = await anext(generator)
        await generator.aclose()
        return frame

    assert asyncio.run(read_heartbeat()).startswith("event: heartbeat\n")

    disconnected_fake = FakeSupabase([])

    async def verify_disconnect() -> None:
        async def disconnected() -> bool:
            return True

        generator = stream_event_logs(
            disconnected_fake,  # type: ignore[arg-type]
            last_event_id=0,
            is_disconnected=disconnected,
        )
        with pytest.raises(StopAsyncIteration):
            await anext(generator)

    asyncio.run(verify_disconnect())


def test_event_filter_rejects_naive_or_reversed_period() -> None:
    with pytest.raises(ValueError):
        EventLogFilter(start_at=datetime(2026, 8, 7, 0, 0))
    with pytest.raises(ValueError):
        EventLogFilter(
            start_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
            end_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        )
