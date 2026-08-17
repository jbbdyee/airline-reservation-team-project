"""백엔드 관리자 항공편 API 요청 함수."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.api_client import as_list, request


KST = ZoneInfo("Asia/Seoul")

STATUS_LABELS = {
    "SCHEDULED": "정상",
    "DELAYED": "지연",
    "CANCELLED": "결항",
    "DEPARTED": "출발",
}


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(KST)


def _airport_label(airport: dict) -> str:
    return (
        f"{airport['city']}"
        f"({airport['iata_code']})"
    )


def _normalize_flight(flight: dict) -> dict:
    """백엔드 응답을 관리자 화면용 데이터로 변환합니다."""

    departure = _parse_datetime(
        flight["departure_at"]
    )
    arrival = _parse_datetime(
        flight["arrival_at"]
    )

    origin = flight["origin"]
    destination = flight["destination"]

    return {
        "id": flight["id"],
        "flight_no": flight["flight_number"],
        "route": (
            f"{_airport_label(origin)} → "
            f"{_airport_label(destination)}"
        ),
        "departure": departure.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "arrival": arrival.strftime(
            "%Y-%m-%d %H:%M"
        ),
        "status": STATUS_LABELS.get(
            flight["status"],
            flight["status"],
        ),
        "status_code": flight["status"],
        "base_price": flight["base_price"],
        "lowest_seat_price": flight[
            "lowest_seat_price"
        ],
        "available_seats": flight[
            "available_seats"
        ],
        "origin_airport_id": origin["id"],
        "destination_airport_id": destination["id"],
        "origin_airport": origin,
        "destination_airport": destination,
        "departure_at": flight["departure_at"],
        "arrival_at": flight["arrival_at"],
    }


def get_flights(
    flight_number: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> list[dict]:
    params = {
        "page": page,
        "page_size": page_size,
    }

    if flight_number:
        params["flight_number"] = (
            flight_number.strip().upper()
        )

    if status:
        params["status"] = status

    payload = request(
        "GET",
        "/admin/flights",
        params=params,
    )

    return [
        _normalize_flight(flight)
        for flight in as_list(payload)
    ]


def create_flight(flight: dict) -> dict:
    created = request(
        "POST",
        "/flights",
        json=flight,
    )

    return _normalize_flight(created)


def update_flight(
    flight_id: str,
    flight: dict,
) -> dict:
    updated = request(
        "PUT",
        f"/flights/{flight_id}",
        json=flight,
    )

    return _normalize_flight(updated)


def delete_flight(
    flight_id: str,
) -> None:
    request(
        "DELETE",
        f"/flights/{flight_id}",
    )