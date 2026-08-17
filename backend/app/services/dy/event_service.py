"""이벤트 로그 조회와 DB 폴링 기반 SSE 스트림."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from uuid import UUID

from anyio import to_thread
from supabase import Client

from app.schemas.dy.event_schema import EventLogFilter, EventLogPage, EventLogRead


EVENT_COLUMNS = (
    "id,event_type,resource_id,flight_id,booking_id,"
    "actor_user_id,payload,created_at"
)


class EventLogNotFoundError(Exception):
    pass


def _serialize_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def list_event_logs(client: Client, filters: EventLogFilter) -> EventLogPage:
    """관리자 조건에 맞는 이벤트 로그를 최신순으로 조회한다."""

    query = client.table("event_logs").select(EVENT_COLUMNS, count="exact")
    if filters.event_type is not None:
        query = query.eq("event_type", filters.event_type.value)
    if filters.flight_id is not None:
        query = query.eq("flight_id", str(filters.flight_id))
    if filters.booking_id is not None:
        query = query.eq("booking_id", str(filters.booking_id))
    if filters.start_at is not None:
        query = query.gte("created_at", _serialize_utc_timestamp(filters.start_at))
    if filters.end_at is not None:
        query = query.lte("created_at", _serialize_utc_timestamp(filters.end_at))

    start = (filters.page - 1) * filters.page_size
    response = (
        query.order("created_at", desc=True)
        .range(start, start + filters.page_size - 1)
        .execute()
    )
    total = response.count or 0
    return EventLogPage(
        items=[EventLogRead.model_validate(row) for row in response.data or []],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=math.ceil(total / filters.page_size) if total else 0,
    )


def get_event_log(client: Client, event_log_id: int) -> EventLogRead:
    response = (
        client.table("event_logs")
        .select(EVENT_COLUMNS)
        .eq("id", event_log_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise EventLogNotFoundError
    return EventLogRead.model_validate(rows[0])


def get_latest_event_id(client: Client) -> int:
    """새 SSE 연결이 과거 전체 로그를 재전송하지 않도록 현재 cursor를 얻는다."""

    response = (
        client.table("event_logs")
        .select("id")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return int(rows[0]["id"]) if rows else 0


def fetch_events_after(
    client: Client,
    last_event_id: int,
    flight_id: UUID | None = None,
    batch_size: int = 100,
) -> list[EventLogRead]:
    """cursor 이후 로그를 ID 오름차순으로 가져온다."""

    query = (
        client.table("event_logs")
        .select(EVENT_COLUMNS)
        .gt("id", last_event_id)
    )
    if flight_id is not None:
        query = query.eq("flight_id", str(flight_id))
    response = query.order("id").limit(batch_size).execute()
    return [EventLogRead.model_validate(row) for row in response.data or []]


def _sse_event(event: EventLogRead) -> str:
    event_name = event.event_type.value.lower()
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"id: {event.id}\nevent: {event_name}\ndata: {data}\n\n"


def _sse_heartbeat() -> str:
    data = json.dumps(
        {"created_at": datetime.now(timezone.utc).isoformat()},
        ensure_ascii=False,
    )
    return f"event: heartbeat\ndata: {data}\n\n"


async def stream_event_logs(
    client: Client,
    last_event_id: int,
    flight_id: UUID | None = None,
    *,
    poll_interval: float = 1.0,
    heartbeat_interval: float = 15.0,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[str]:
    """event_logs를 폴링해 SSE frame을 생성한다.

    Supabase Python Client가 동기 방식이므로 DB 조회는 worker thread에서
    실행해 다른 FastAPI 요청과 SSE 연결을 막지 않는다.
    """

    cursor = last_event_id
    last_sent_at = monotonic()
    while True:
        if is_disconnected is not None and await is_disconnected():
            return

        events = await to_thread.run_sync(
            lambda: fetch_events_after(client, cursor, flight_id)
        )
        if events:
            for event in events:
                cursor = max(cursor, event.id)
                last_sent_at = monotonic()
                yield _sse_event(event)
            continue

        if monotonic() - last_sent_at >= heartbeat_interval:
            last_sent_at = monotonic()
            yield _sse_heartbeat()

        await asyncio.sleep(poll_interval)
