"""사용자 항공편 검색 및 좌석 조회 API 클라이언트."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.api_client import BackendAPIError, request


KST = ZoneInfo("Asia/Seoul")


def _parse_datetime(value: str) -> datetime:
    """백엔드 UTC 시간을 한국 시간으로 변환합니다."""

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(KST)


def _airport_label(airport: dict) -> str:
    """공항 정보를 화면 표시 형식으로 변환합니다."""

    city = str(airport.get("city", ""))
    iata_code = str(airport.get("iata_code", ""))

    if city:
        return f"{city}({iata_code})"

    return iata_code


def _sort_params(sort_by: str) -> tuple[str, str]:
    """화면 정렬 값을 백엔드 쿼리 값으로 변환합니다."""

    sort_mapping = {
        "가격 낮은 순": ("price", "asc"),
        "가격 높은 순": ("price", "desc"),
        "출발 시간 빠른 순": ("departure_at", "asc"),
    }

    return sort_mapping.get(sort_by, ("price", "asc"))


def _fetch_flights(
    origin: str,
    destination: str,
    departure_date: date,
    passengers: int,
    cabin_class: str,
    sort_field: str,
    sort_order: str,
) -> list[dict]:
    """한 좌석 등급에 해당하는 항공편을 조회합니다."""

    payload = request(
        "GET",
        "/flights",
        params={
            "origin": origin,
            "destination": destination,
            "date": departure_date.isoformat(),
            "passengers": passengers,
            "cabin_class": cabin_class,
            "sort_by": sort_field,
            "sort_order": sort_order,
        },
    )

    if not isinstance(payload, list):
        return []

    return [
        flight
        for flight in payload
        if isinstance(flight, dict)
    ]


def _fetch_all_cabin_classes(
    origin: str,
    destination: str,
    departure_date: date,
    passengers: int,
    sort_field: str,
    sort_order: str,
) -> list[dict]:
    """이코노미와 비즈니스 검색 결과를 합칩니다."""

    merged: dict[str, dict[str, Any]] = {}

    for cabin_class in ("ECONOMY", "BUSINESS"):
        flights = _fetch_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            passengers=1,
            cabin_class=cabin_class,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        for flight in flights:
            flight_id = str(flight.get("id", ""))

            if not flight_id:
                continue

            if flight_id not in merged:
                merged[flight_id] = dict(flight)
                continue

            saved_flight = merged[flight_id]

            saved_flight["available_seats"] = (
                int(saved_flight.get("available_seats", 0))
                + int(flight.get("available_seats", 0))
            )

            saved_flight["lowest_seat_price"] = min(
                int(
                    saved_flight.get(
                        "lowest_seat_price",
                        flight["lowest_seat_price"],
                    )
                ),
                int(flight["lowest_seat_price"]),
            )

    # 인원수보다 좌석이 적은 항공편도 결과에 유지합니다.
    flights = list(merged.values())

    if sort_field == "price":
        flights.sort(
            key=lambda flight: int(
                flight.get("lowest_seat_price", 0)
            ),
            reverse=sort_order == "desc",
        )
    else:
        flights.sort(
            key=lambda flight: _parse_datetime(
                flight["departure_at"]
            ),
            reverse=sort_order == "desc",
        )

    return flights


def _normalize_flight(
    flight: dict,
    passengers: int,
    cabin_class: str,
) -> dict:
    """백엔드 항공편 응답을 기존 화면 형식으로 변환합니다."""

    departure_at = _parse_datetime(flight["departure_at"])
    arrival_at = _parse_datetime(flight["arrival_at"])

    origin_airport = flight.get("origin", {})
    destination_airport = flight.get("destination", {})

    return {
        # 기존 화면에서 사용하는 필드
        "flight_id": flight["id"],
        "airline": flight.get("airline", "SkyOps"),
        "flight_no": flight["flight_number"],
        "origin": _airport_label(origin_airport),
        "destination": _airport_label(destination_airport),
        "departure_date": departure_at.date().isoformat(),
        "departure_time": departure_at.strftime("%H:%M"),
        "arrival_time": arrival_at.strftime("%H:%M"),
        "price": int(flight["lowest_seat_price"]),
        "passengers": passengers,
        "cabin_class": cabin_class,
        "remaining_seats": int(flight["available_seats"]),

        # 백엔드 원본 필드
        "id": flight["id"],
        "flight_number": flight["flight_number"],
        "origin_airport": origin_airport,
        "destination_airport": destination_airport,
        "departure_at": flight["departure_at"],
        "arrival_at": flight["arrival_at"],
        "status": flight["status"],
        "base_price": flight["base_price"],
        "lowest_seat_price": flight["lowest_seat_price"],
        "available_seats": flight["available_seats"],
    }


def search_flights(
    origin: str,
    destination: str,
    departure_date: date,
    passengers: int,
    cabin_class: str,
    sort_by: str,
) -> list[dict]:
    """백엔드를 통해 Supabase 항공편을 검색합니다."""

    origin = origin.strip().upper()
    destination = destination.strip().upper()

    if origin == destination:
        return []

    if passengers < 1 or passengers > 9:
        raise BackendAPIError(
            "승객 수는 1명 이상 9명 이하여야 합니다."
        )

    sort_field, sort_order = _sort_params(sort_by)

    if cabin_class == "ALL":
        raw_flights = _fetch_all_cabin_classes(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            passengers=passengers,
            sort_field=sort_field,
            sort_order=sort_order,
        )
    else:
        # 백엔드는 인원수보다 좌석이 적으면 결과에서 제외하므로,
        # 1석 이상 남은 항공편은 모두 받아 화면에서 부족 여부를 표시합니다.
        raw_flights = _fetch_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            passengers=1,
            cabin_class=cabin_class,
            sort_field=sort_field,
            sort_order=sort_order,
        )

    return [
        _normalize_flight(
            flight=flight,
            passengers=passengers,
            cabin_class=cabin_class,
        )
        for flight in raw_flights
    ]


def _seat_sort_key(seat: dict) -> tuple[int, str]:
    """좌석을 1A, 1B, 2A 순서로 정렬합니다."""

    seat_number = str(seat.get("seat_number", ""))

    try:
        return (
            int(seat_number[:-1]),
            seat_number[-1],
        )
    except (ValueError, IndexError):
        return (
            10_000,
            seat_number,
        )


def _normalize_seat(seat: dict) -> dict:
    """백엔드 좌석 응답을 기존 좌석 화면 형식으로 변환합니다."""

    backend_status = str(seat.get("status", ""))

    frontend_status = (
        "AVAILABLE"
        if backend_status == "AVAILABLE"
        else "RESERVED"
    )

    seat_number = str(seat.get("seat_number", ""))

    return {
        "id": seat.get("id"),
        "flight_id": seat.get("flight_id"),
        "seat_number": seat_number,
        "seat_no": seat_number,
        "cabin_class": seat.get("cabin_class"),
        "price": int(seat.get("price", 0)),
        "status": frontend_status,
        "backend_status": backend_status,
    }


def get_flight_seats(
    flight_id: str,
    cabin_class: str = "ALL",
) -> list[dict]:
    """선택한 항공편의 실제 좌석을 백엔드에서 조회합니다."""

    params: dict[str, str] = {}

    if cabin_class != "ALL":
        params["cabin_class"] = cabin_class

    payload = request(
        "GET",
        f"/flights/{flight_id}/seats",
        params=params,
    )

    if not isinstance(payload, list):
        return []

    seats = [
        _normalize_seat(seat)
        for seat in payload
        if isinstance(seat, dict)
    ]

    seats.sort(key=_seat_sort_key)

    return seats