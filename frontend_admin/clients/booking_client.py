"""기존 예약 관리 화면과 백엔드 API를 연결하는 클라이언트."""

from __future__ import annotations

from typing import Any

from core.api_client import as_list, request


STATUS_TO_API = {
    "확정": "CONFIRMED",
    "취소": "CANCELLED",
}

STATUS_TO_FRONTEND = {
    "CONFIRMED": "확정",
    "CANCELLED": "취소",
}


def _normalize_booking(
    booking: dict[str, Any],
) -> dict[str, Any]:
    """
    백엔드의 중첩된 예약 데이터를 기존 화면이 사용하는
    평면 데이터로 변환합니다.
    """

    flight = booking.get("flight") or {}
    seat = booking.get("seat") or {}

    origin = flight.get("origin") or {}
    destination = flight.get("destination") or {}

    backend_status = str(
        booking.get("status", "")
    ).upper()

    return {
        # 상태 변경 API에 실제 UUID가 필요하므로 id는 유지
        "id": booking.get("id", ""),

        # 화면에 추가로 표시 가능한 예약번호
        "booking_code": booking.get(
            "booking_code",
            "",
        ),

        # 기존 페이지가 사용하는 필드 이름
        "passenger": booking.get(
            "passenger_name",
            "",
        ),
        "flight_no": flight.get(
            "flight_number",
            "",
        ),
        "flight_id": flight.get(
            "id",
            "",
        ),
        "seat_number": seat.get(
            "seat_number",
            "",
        ),
        "status": STATUS_TO_FRONTEND.get(
            backend_status,
            backend_status,
        ),
        "amount": booking.get(
            "total_price",
            0,
        ),
        "created_at": booking.get(
            "created_at",
            "",
        ),

        # 기존 화면에서도 확인할 수 있는 추가 정보
        "origin": origin.get(
            "iata_code",
            "",
        ),
        "destination": destination.get(
            "iata_code",
            "",
        ),
        "departure_at": flight.get(
            "departure_at",
            "",
        ),
        "cabin_class": seat.get(
            "cabin_class",
            "",
        ),
        "cancelled_at": booking.get(
            "cancelled_at",
        ),
    }


def get_admin_bookings(
    status: str | None = None,
    page: int = 1,
) -> list[dict]:
    """
    기존 페이지 함수 형태를 유지하면서 실제 예약을 조회합니다.

    반환값도 기존 페이지가 기대하는 list[dict] 형식입니다.
    """

    params: dict[str, Any] = {
        "page": page,
        "page_size": 100,
    }

    # None을 전송하면 Enum 검증에서 문제가 생길 수 있으므로
    # 상태가 선택된 경우에만 쿼리에 포함합니다.
    if status:
        params["status"] = STATUS_TO_API.get(
            status,
            status.upper(),
        )

    payload = request(
        "GET",
        "/admin/bookings",
        params=params,
    )

    raw_bookings = as_list(payload)

    return [
        _normalize_booking(booking)
        for booking in raw_bookings
        if isinstance(booking, dict)
    ]


def update_booking_status(
    booking_id: str,
    status: str,
) -> dict:
    """
    기존 화면의 한글 상태를 백엔드 Enum으로 변환합니다.
    """

    backend_status = STATUS_TO_API.get(
        status,
        status.upper(),
    )

    payload = request(
        "PUT",
        f"/admin/bookings/{booking_id}/status",
        json={
            "status": backend_status,
        },
    )

    if not isinstance(payload, dict):
        return {}

    return _normalize_booking(payload)