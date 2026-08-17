"""관리자 운영 대시보드 집계 로직."""

from __future__ import annotations

from datetime import datetime, timezone

from supabase import Client

from app.schemas.dy.admin_schema import (
    AdminDashboardRead,
    BookingMetrics,
    DashboardFilter,
    FlightMetrics,
)
from app.schemas.dy.event_schema import EventLogRead
from app.services.dy.event_service import EVENT_COLUMNS
from app.services.dy.feedback_service import summarize_chat_feedbacks


def _serialize_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def _apply_period(query, filters: DashboardFilter):
    if filters.start_at is not None:
        query = query.gte("created_at", _serialize_utc(filters.start_at))
    if filters.end_at is not None:
        query = query.lte("created_at", _serialize_utc(filters.end_at))
    return query


def get_admin_dashboard(
    client: Client,
    filters: DashboardFilter,
    recent_event_limit: int = 10,
) -> AdminDashboardRead:
    """운항·예약·챗봇 품질·최근 이벤트 지표를 한 번에 반환한다."""

    flight_rows = client.table("flights").select("status").execute().data or []
    flight_statuses = [row["status"] for row in flight_rows]

    booking_query = client.table("bookings").select("status,total_price,created_at")
    booking_query = _apply_period(booking_query, filters)
    booking_rows = booking_query.execute().data or []
    confirmed_bookings = [
        row for row in booking_rows if row["status"] == "CONFIRMED"
    ]

    chat_summary = summarize_chat_feedbacks(
        client,
        start_at=filters.start_at,
        end_at=filters.end_at,
    )

    event_query = client.table("event_logs").select(EVENT_COLUMNS)
    event_query = _apply_period(event_query, filters)
    event_rows = (
        event_query.order("created_at", desc=True)
        .limit(recent_event_limit)
        .execute()
        .data
        or []
    )

    return AdminDashboardRead(
        flights=FlightMetrics(
            total=len(flight_statuses),
            scheduled=flight_statuses.count("SCHEDULED"),
            delayed=flight_statuses.count("DELAYED"),
            cancelled=flight_statuses.count("CANCELLED"),
            departed=flight_statuses.count("DEPARTED"),
        ),
        bookings=BookingMetrics(
            total=len(booking_rows),
            confirmed=len(confirmed_bookings),
            cancelled=sum(row["status"] == "CANCELLED" for row in booking_rows),
            confirmed_revenue=sum(
                int(row["total_price"]) for row in confirmed_bookings
            ),
        ),
        chat_feedbacks=chat_summary,
        recent_events=[EventLogRead.model_validate(row) for row in event_rows],
    )
