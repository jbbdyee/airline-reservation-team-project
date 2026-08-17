"""기존 사용자 예약 화면과 실제 백엔드 API를 연결하는 클라이언트."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from clients.flight_client import get_flight_seats
from core.api_client import BackendAPIError, request


KST = ZoneInfo("Asia/Seoul")


def _parse_datetime(
    value: str | datetime | None,
) -> datetime | None:
    """백엔드 날짜를 한국 시간 datetime으로 변환합니다."""

    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(KST)


def _airport_label(
    airport: dict[str, Any] | None,
) -> str:
    if not airport:
        return "-"

    city = airport.get("city", "")
    code = airport.get("iata_code", "")
    name = str(
        airport.get(
            "name",
            "",
        )
    )
    if city and code:
        return f"{city}({code})"

    return code or city or name or "-"


def _extract_items(
    payload: Any,
) -> list[dict]:
    """페이지 응답에서 예약 목록을 추출합니다."""

    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if isinstance(payload, dict):
        items = payload.get(
            "items",
            [],
        )

        if isinstance(items, list):
            return [
                item
                for item in items
                if isinstance(item, dict)
            ]

    return []


def _normalize_booking(
    booking: dict[str, Any],
) -> dict[str, Any]:
    """
    백엔드 예약 응답을 기존 booking_card.py가 사용하는
    데이터 형식으로 변환합니다.
    """

    flight = booking.get("flight") or {}
    seat = booking.get("seat") or {}

    departure_at = _parse_datetime(
        flight.get("departure_at")
    )

    created_at = _parse_datetime(
        booking.get("created_at")
    )

    cancelled_at = _parse_datetime(
        booking.get("cancelled_at")
    )

    origin = _airport_label(
        flight.get("origin")
    )

    destination = _airport_label(
        flight.get("destination")
    )

    return {
        # 예약 취소 API에서 실제 UUID가 필요합니다.
        "booking_id": booking.get("id", ""),

        # 사용자에게 보여줄 수 있는 별도 예약 코드
        "booking_code": booking.get(
            "booking_code",
            "",
        ),

        "user_id": booking.get("user_id", ""),
        "flight_id": flight.get("id", ""),
        "flight_no": flight.get(
            "flight_number",
            "",
        ),
        "route": f"{origin} → {destination}",
        "departure_date": (
            departure_at.date().isoformat()
            if departure_at
            else ""
        ),
        "departure_time": (
            departure_at.strftime("%H:%M")
            if departure_at
            else ""
        ),
        "seat_number": seat.get(
            "seat_number",
            "",
        ),
        "passenger_name": booking.get(
            "passenger_name",
            "",
        ),
        "price": booking.get(
            "total_price",
            seat.get("price", 0),
        ),
        "status": booking.get(
            "status",
            "CONFIRMED",
        ),

        # 현재 백엔드 응답에는 취소 사유가 포함되지 않습니다.
        "cancel_reason": booking.get(
            "cancel_reason",
            "",
        ) or "",
        "cancelled_at": cancelled_at,
        "created_at": created_at or datetime.now(KST),

        # 추가 원본 정보
        "seat_id": seat.get("id", ""),
        "cabin_class": seat.get(
            "cabin_class",
            "",
        ),
        "flight_status": flight.get(
            "status",
            "",
        ),
    }


def _validate_passengers(
    flight: dict,
    passenger_details: list[dict],
) -> None:
    expected_passengers = int(
        flight.get(
        "passengers",
        1,
        )
    )
    if len(passenger_details) != expected_passengers:
        raise BackendAPIError(
            f"승객 정보를 {expected_passengers}명 입력해 주세요."
        )

    seat_numbers = [str(
        passenger.get("seat_number", "")).strip()
        for passenger in passenger_details
        
    ]

    if any(
        not seat_number
        for seat_number in seat_numbers
    ):
        raise BackendAPIError(
            "선택되지 않은 좌석이 있습니다."
        )
    
    if len(set(seat_numbers)) != len(seat_numbers):
        raise BackendAPIError(
            "중복된 좌석이 선택되었습니다."
        )

    for passenger in passenger_details:
        passenger_name = str(
            passenger.get(
                "name",
                "",
            )
        ).strip()

        if not passenger_name:
            raise BackendAPIError(
                "모든 승객 이름을 입력해 주세요."
            )


def create_bookings(
    user_id: str,
    flight: dict,
    passenger_details: list[dict],
) -> list[dict]:
    """
    기존 예약 페이지 호출 형태를 유지하면서
    승객별 예약을 실제 백엔드에 등록합니다.
    """

    # 백엔드는 Authorization 토큰으로 사용자를 식별합니다.
    del user_id

    _validate_passengers(
        flight,
        passenger_details,
    )

    flight_id = flight.get(
        "flight_id",
        flight.get("id"),
    )

    if not flight_id:
        raise BackendAPIError(
            "항공편 ID가 없습니다. "
            "항공편을 다시 선택해 주세요."
        )

    # 기존 화면은 좌석 번호만 보관하므로,
    # 실제 좌석 목록을 다시 조회해 UUID를 찾습니다.
    seats = get_flight_seats(
        flight_id,
        "ALL",
    )

    seats_by_number = {
        str(seat["seat_number"]): seat
        for seat in seats
        if seat.get("seat_number")
    }

    selected_seat_numbers = [
        passenger["seat_number"]
        for passenger in passenger_details
    ]

    # API 호출 전에 모든 좌석을 먼저 검증합니다.
    for seat_number in selected_seat_numbers:
        seat = seats_by_number.get(seat_number)

        if not seat:
            raise BackendAPIError(
                f"{seat_number} 좌석을 찾을 수 없습니다."
            )

        backend_status = seat.get(
            "backend_status",
            seat.get("status"),
        )

        if backend_status != "AVAILABLE":
            raise BackendAPIError(
                f"{seat_number} 좌석은 현재 예약할 수 없습니다."
            )

        if not seat.get("id"):
            raise BackendAPIError(
                f"{seat_number} 좌석의 ID가 없습니다."
            )

    created_bookings: list[dict] = []

    # 백엔드는 예약 한 건당 승객 한 명과 좌석 한 개를 받습니다.
    for passenger in passenger_details:
        seat_number = passenger["seat_number"]
        seat = seats_by_number[seat_number]
        passenger_name = str(
            passenger["name"]
        ).strip()


        payload = request(
            "POST",
            "/bookings",
            json={
                "flight_id": flight_id,
                "seat_id": seat["id"],
                "passenger_name": (
                    passenger_name
                ),
            },
        )

        if not isinstance(payload, dict):
            raise BackendAPIError(
                f"{seat_number} 좌석 예약 응답이 올바르지 않습니다."
            )

        created_bookings.append(
            _normalize_booking(payload)
        )

    return created_bookings


def get_my_bookings(
    user_id: str,
) -> list[dict]:
    """
    기존 내 예약 화면 호출 형태를 유지하면서
    실제 로그인 사용자의 예약을 조회합니다.
    """

    # 백엔드는 세션 토큰으로 사용자를 판단합니다.
    del user_id

    payload = request(
        "GET",
        "/bookings/me",
        params={
            "page": 1,
            "page_size": 100,
        },
    )

    return [
        _normalize_booking(booking)
        for booking in _extract_items(payload)
    ]


def cancel_booking(
    user_id: str,
    booking_id: str,
    reason: str,
) -> None:
    """
    기존 예약 카드 호출 형태를 유지하면서
    실제 예약을 취소합니다.
    """

    del user_id

    normalized_reason = reason.strip()

    if len(normalized_reason) < 2:
        raise BackendAPIError(
            "예약 취소 사유는 최소 2글자 이상 입력해 주세요."
        )

    if not booking_id:
        raise BackendAPIError(
            "예약 ID가 없습니다."
        )

    request(
        "PUT",
        f"/bookings/{booking_id}/cancel",
        json={
            "reason": normalized_reason,
        },
    )
