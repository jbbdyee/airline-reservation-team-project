"""항공편 검색·상세 조회 비즈니스 로직."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from supabase import Client

from app.schemas.dy.flight_schema import (
    AdminFlightFilter,
    CabinClass,
    FlightCreate,
    FlightDetail,
    FlightSearchParams,
    FlightSortField,
    FlightSummary,
    FlightPage,
    FlightUpdate,
    SeatAvailability,
    SortOrder,
)


KST = ZoneInfo("Asia/Seoul")
FLIGHT_SELECT = ",".join(
    (
        "id",
        "flight_number",
        "departure_at",
        "arrival_at",
        "status",
        "base_price",
        "origin:airports!flights_origin_airport_id_fkey!inner(id,iata_code,name,city,country)",
        "destination:airports!flights_destination_airport_id_fkey!inner(id,iata_code,name,city,country)",
        "seats(id,cabin_class,price,status)",
    )
)


class FlightNotFoundError(Exception):
    """요청한 항공편이 없을 때 발생한다."""


class FlightConflictError(Exception):
    """같은 편명·출발시각의 항공편이 이미 있을 때 발생한다."""


class FlightInUseError(Exception):
    """좌석 또는 예약이 연결된 항공편을 삭제하려 할 때 발생한다."""


class InvalidFlightStateError(Exception):
    """부분 수정 결과가 항공편 무결성 규칙을 위반할 때 발생한다."""


def _utc_search_range(search_date) -> tuple[datetime, datetime]:
    """한국 날짜 하루를 `[start, end)` UTC 범위로 변환한다."""

    start_kst = datetime.combine(search_date, time.min, tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)


def _available_seats(
    row: dict[str, Any], cabin_class: CabinClass | None = None
) -> list[dict[str, Any]]:
    seats = row.get("seats") or []
    return [
        seat
        for seat in seats
        if seat.get("status") == "AVAILABLE"
        and (cabin_class is None or seat.get("cabin_class") == cabin_class.value)
    ]


def _to_summary(
    row: dict[str, Any], cabin_class: CabinClass
) -> FlightSummary | None:
    seats = _available_seats(row, cabin_class)
    if not seats:
        return None

    return FlightSummary(
        id=row["id"],
        flight_number=row["flight_number"],
        origin=row["origin"],
        destination=row["destination"],
        departure_at=row["departure_at"],
        arrival_at=row["arrival_at"],
        status=row["status"],
        base_price=row["base_price"],
        lowest_seat_price=min(seat["price"] for seat in seats),
        available_seats=len(seats),
    )


def _to_detail(row: dict[str, Any]) -> FlightDetail:
    """DB 조회 행을 관리자·사용자 공통 상세 응답으로 변환한다."""

    all_available = _available_seats(row)
    representative_price = min(
        (seat["price"] for seat in all_available), default=row["base_price"]
    )
    by_class: dict[CabinClass, SeatAvailability] = {}
    for cabin_class in CabinClass:
        seats = _available_seats(row, cabin_class)
        by_class[cabin_class] = SeatAvailability(
            available_seats=len(seats),
            lowest_price=min((seat["price"] for seat in seats), default=None),
        )

    return FlightDetail(
        id=row["id"],
        flight_number=row["flight_number"],
        origin=row["origin"],
        destination=row["destination"],
        departure_at=row["departure_at"],
        arrival_at=row["arrival_at"],
        status=row["status"],
        base_price=row["base_price"],
        lowest_seat_price=representative_price,
        available_seats=len(all_available),
        seats_by_cabin_class=by_class,
    )


def search_flights(
    client: Client, params: FlightSearchParams
) -> list[FlightSummary]:
    """검색 조건과 필요한 잔여 좌석 수를 만족하는 항공편을 반환한다."""

    start_at, end_at = _utc_search_range(params.date)
    query = (
        client.table("flights")
        .select(FLIGHT_SELECT)
        .eq("origin.iata_code", params.origin)
        .eq("destination.iata_code", params.destination)
        .gte("departure_at", start_at.isoformat())
        .lt("departure_at", end_at.isoformat())
        .in_("status", ["SCHEDULED", "DELAYED"])
        .eq("seats.cabin_class", params.cabin_class.value)
        .eq("seats.status", "AVAILABLE")
    )
    response = query.execute()

    flights: list[FlightSummary] = []
    for row in response.data or []:
        summary = _to_summary(row, params.cabin_class)
        if summary is not None and summary.available_seats >= params.passengers:
            flights.append(summary)

    if params.sort_by is FlightSortField.PRICE:
        sort_key = lambda flight: (flight.lowest_seat_price, flight.departure_at)
    else:
        sort_key = lambda flight: (flight.departure_at, flight.lowest_seat_price)

    return sorted(
        flights,
        key=sort_key,
        reverse=params.sort_order is SortOrder.DESC,
    )


def list_admin_flights(
    client: Client,
    filters: AdminFlightFilter,
) -> FlightPage:
    """관리자가 운항 상태와 편명으로 전체 항공편을 조회한다."""

    query = client.table("flights").select(FLIGHT_SELECT, count="exact")
    if filters.flight_number is not None:
        query = query.ilike("flight_number", f"%{filters.flight_number}%")
    if filters.status is not None:
        query = query.eq("status", filters.status.value)

    start = (filters.page - 1) * filters.page_size
    response = (
        query.order("departure_at", desc=True)
        .range(start, start + filters.page_size - 1)
        .execute()
    )
    total = response.count or 0
    return FlightPage(
        items=[_to_detail(row) for row in response.data or []],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=math.ceil(total / filters.page_size) if total else 0,
    )


def get_flight(client: Client, flight_id: UUID) -> FlightDetail:
    """항공편과 등급별 예약 가능 좌석 집계를 반환한다."""

    response = (
        client.table("flights")
        .select(FLIGHT_SELECT)
        .eq("id", str(flight_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise FlightNotFoundError

    return _to_detail(rows[0])


def _serialize_utc_timestamp(value: datetime) -> str:
    """timestamp 컬럼에 넣을 UTC 시각을 timezone 없는 ISO 문자열로 만든다."""

    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def _create_payload(data: FlightCreate) -> dict[str, Any]:
    return {
        "flight_number": data.flight_number,
        "origin_airport_id": str(data.origin_airport_id),
        "destination_airport_id": str(data.destination_airport_id),
        "departure_at": _serialize_utc_timestamp(data.departure_at),
        "arrival_at": _serialize_utc_timestamp(data.arrival_at),
        "status": data.status.value,
        "base_price": data.base_price,
    }


def _flight_schedule_exists(
    client: Client,
    flight_number: str,
    departure_at: str,
    exclude_flight_id: UUID | None = None,
) -> bool:
    query = (
        client.table("flights")
        .select("id")
        .eq("flight_number", flight_number)
        .eq("departure_at", departure_at)
    )
    if exclude_flight_id is not None:
        query = query.neq("id", str(exclude_flight_id))
    response = query.limit(1).execute()
    return bool(response.data)


def _get_mutation_row(client: Client, flight_id: UUID) -> dict[str, Any]:
    response = (
        client.table("flights")
        .select(
            "id,flight_number,origin_airport_id,destination_airport_id,"
            "departure_at,arrival_at,status,base_price"
        )
        .eq("id", str(flight_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise FlightNotFoundError
    return rows[0]


def create_flight(client: Client, data: FlightCreate) -> FlightDetail:
    """관리자가 새 항공편을 생성한다."""

    payload = _create_payload(data)
    if _flight_schedule_exists(
        client,
        data.flight_number,
        payload["departure_at"],
    ):
        raise FlightConflictError

    response = client.table("flights").insert(payload).execute()
    rows = response.data or []
    if not rows or not rows[0].get("id"):
        raise RuntimeError("항공편 생성 결과에 ID가 없습니다.")
    return get_flight(client, UUID(rows[0]["id"]))


def update_flight(
    client: Client,
    flight_id: UUID,
    data: FlightUpdate,
    actor_user_id: UUID,
) -> FlightDetail:
    """항공편을 부분 수정하고 운항 상태 변경 로그를 기록한다."""

    current = _get_mutation_row(client, flight_id)
    changes = data.model_dump(exclude_unset=True)

    final_origin = str(changes.get("origin_airport_id", current["origin_airport_id"]))
    final_destination = str(
        changes.get("destination_airport_id", current["destination_airport_id"])
    )
    if final_origin == final_destination:
        raise InvalidFlightStateError("출발 공항과 도착 공항은 달라야 합니다.")

    departure = changes.get("departure_at")
    if departure is None:
        departure_value = datetime.fromisoformat(current["departure_at"])
        if departure_value.tzinfo is None:
            departure_value = departure_value.replace(tzinfo=timezone.utc)
    else:
        departure_value = departure

    arrival = changes.get("arrival_at")
    if arrival is None:
        arrival_value = datetime.fromisoformat(current["arrival_at"])
        if arrival_value.tzinfo is None:
            arrival_value = arrival_value.replace(tzinfo=timezone.utc)
    else:
        arrival_value = arrival

    if arrival_value <= departure_value:
        raise InvalidFlightStateError("도착 시각은 출발 시각보다 늦어야 합니다.")

    flight_number = changes.get("flight_number", current["flight_number"])
    departure_at = _serialize_utc_timestamp(departure_value)
    if _flight_schedule_exists(
        client,
        flight_number,
        departure_at,
        exclude_flight_id=flight_id,
    ):
        raise FlightConflictError

    payload: dict[str, Any] = {}
    for field, value in changes.items():
        if isinstance(value, UUID):
            payload[field] = str(value)
        elif isinstance(value, datetime):
            payload[field] = _serialize_utc_timestamp(value)
        elif hasattr(value, "value"):
            payload[field] = value.value
        else:
            payload[field] = value

    client.table("flights").update(payload).eq("id", str(flight_id)).execute()

    new_status = payload.get("status")
    previous_status = current["status"]
    if new_status is not None and new_status != previous_status:
        client.table("event_logs").insert(
            {
                "event_type": "FLIGHT_STATUS_CHANGED",
                "resource_id": str(flight_id),
                "flight_id": str(flight_id),
                "booking_id": None,
                "actor_user_id": str(actor_user_id),
                "payload": {
                    "previous_status": previous_status,
                    "status": new_status,
                },
            }
        ).execute()

    return get_flight(client, flight_id)


def delete_flight(client: Client, flight_id: UUID) -> None:
    """연결된 좌석·예약이 없는 항공편만 삭제한다."""

    _get_mutation_row(client, flight_id)
    for table in ("bookings", "seats"):
        response = (
            client.table(table)
            .select("id")
            .eq("flight_id", str(flight_id))
            .limit(1)
            .execute()
        )
        if response.data:
            raise FlightInUseError

    client.table("flights").delete().eq("id", str(flight_id)).execute()
