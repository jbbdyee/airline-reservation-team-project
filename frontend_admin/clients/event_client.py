"""기존 실시간 모니터와 이벤트 로그 API를 연결하는 클라이언트."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from core.api_client import BACKEND_URL, as_list, request


SUPPORTED_EVENT_TYPES = {
    "FLIGHT_STATUS_CHANGED",
    "SEAT_CHANGED",
    "BOOKING_CHANGED",
}


def _to_timezone_datetime(
    value: str | None,
    *,
    end_of_day: bool = False,
) -> str | None:
    if not value:
        return None

    # 기존 페이지가 YYYY-MM-DD를 전달하면
    # 한국 시간대가 포함된 datetime으로 바꿉니다.
    try:
        parsed_date = date.fromisoformat(value)

        parsed_datetime = datetime.combine(
            parsed_date,
            time.max if end_of_day else time.min,
            tzinfo=ZoneInfo("Asia/Seoul"),
        )

        return parsed_datetime.isoformat()
    except ValueError:
        return value


def _make_summary(
    event_type: str,
    payload: dict[str, Any],
) -> str:
    if payload.get("summary"):
        return str(payload["summary"])

    before = payload.get("before")
    after = payload.get("after")

    if before is not None and after is not None:
        return f"{before} → {after}"

    status = payload.get("status")

    if status is not None:
        return f"상태: {status}"

    return event_type


def _normalize_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    event_type = str(
        event.get("event_type", "")
    )

    payload = event.get("payload")

    if not isinstance(payload, dict):
        payload = {}

    resource_id = event.get("resource_id", "")
    created_at = event.get("created_at", "")

    return {
        "id": event.get("id"),
        "type": event_type,
        "event_type": event_type,
        "target_id": resource_id,
        "resource_id": resource_id,
        "flight_id": event.get("flight_id") or "",
        "booking_id": event.get("booking_id") or "",
        "actor_user_id": event.get(
            "actor_user_id"
        ) or "",
        "payload": payload,
        "data": payload,
        "summary": _make_summary(
            event_type,
            payload,
        ),
        "occurred_at": created_at,
        "created_at": created_at,
    }


def get_event_logs(
    params: dict | None = None,
    *,
    event_type: str | None = None,
    flight_id: str | None = None,
    booking_id: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """관리자 이벤트 로그 목록을 페이지 단위로 조회합니다."""

    source_params = dict(params or {})

    # 기존 params 방식도 호환
    if event_type is None:
        event_type = source_params.get("event_type")

    if flight_id is None:
        flight_id = source_params.get("flight_id")

    if booking_id is None:
        booking_id = source_params.get("booking_id")

    if start_at is None:
        start_at = source_params.get("start_at")

    if end_at is None:
        end_at = source_params.get("end_at")

    page = int(
        source_params.get(
            "page",
            page,
        )
    )

    page_size = int(
        source_params.get(
            "page_size",
            page_size,
        )
    )

    api_params: dict[str, Any] = {
        "page": page,
        "page_size": page_size,
    }

    if event_type:
        if event_type not in SUPPORTED_EVENT_TYPES:
            return {
                "items": [],
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
            }

        api_params["event_type"] = event_type

    if flight_id:
        api_params["flight_id"] = flight_id

    if booking_id:
        api_params["booking_id"] = booking_id

    normalized_start_at = _to_timezone_datetime(
        start_at
    )

    normalized_end_at = _to_timezone_datetime(
        end_at,
        end_of_day=True,
    )

    if normalized_start_at:
        api_params["start_at"] = normalized_start_at

    if normalized_end_at:
        api_params["end_at"] = normalized_end_at

    payload = request(
        "GET",
        "/admin/event-logs",
        params=api_params,
    )

    if not isinstance(payload, dict):
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "total": 0,
            "total_pages": 0,
        }

    raw_items = payload.get("items", [])

    if not isinstance(raw_items, list):
        raw_items = []

    normalized_items = [
        _normalize_event(event)
        for event in raw_items
        if isinstance(event, dict)
    ]

    return {
        "items": normalized_items,
        "page": int(
            payload.get(
                "page",
                page,
            )
        ),
        "page_size": int(
            payload.get(
                "page_size",
                page_size,
            )
        ),
        "total": int(
            payload.get(
                "total",
                len(normalized_items),
            )
        ),
        "total_pages": int(
            payload.get(
                "total_pages",
                0,
            )
        ),
    }


def get_event_log(
    event_log_id: int | str,
) -> dict:
    payload = request(
        "GET",
        f"/admin/event-logs/{event_log_id}",
    )

    if not isinstance(payload, dict):
        return {}

    return _normalize_event(payload)


def get_event_stream_url(
    flight_id: str | None = None,
) -> str:
    query = ""

    if flight_id:
        query = f"?{urlencode({'flight_id': flight_id})}"

    return f"{BACKEND_URL}/events/stream{query}"