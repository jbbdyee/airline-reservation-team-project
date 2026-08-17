"""예약 생성·조회·취소 비즈니스 로직."""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID, uuid4

from postgrest.exceptions import APIError
from supabase import Client

from app.schemas.dy.booking_schema import (
    BookingCancel,
    BookingCreate,
    BookingPage,
    BookingRead,
    BookingStatus,
    BookingStatusUpdate,
)


BOOKING_SELECT = ",".join(
    (
        "id",
        "booking_code",
        "user_id",
        "passenger_name",
        "status",
        "total_price",
        "created_at",
        "cancelled_at",
        "cancel_reason",
        "flight:flights!bookings_flight_id_fkey("
        "id,flight_number,departure_at,arrival_at,status,"
        "origin:airports!flights_origin_airport_id_fkey(id,iata_code,name,city,country),"
        "destination:airports!flights_destination_airport_id_fkey(id,iata_code,name,city,country))",
        "seat:seats!bookings_seat_id_fkey(id,flight_id,seat_number,cabin_class,price,status)",
    )
)


class BookingNotFoundError(Exception):
    pass


class BookingAccessDeniedError(Exception):
    pass


class SeatAlreadyBookedError(Exception):
    pass


class BookingSeatNotFoundError(Exception):
    pass


class BookingFlightNotFoundError(Exception):
    pass


class FlightSeatMismatchError(Exception):
    pass


class FlightNotBookableError(Exception):
    pass


class BookingAlreadyCancelledError(Exception):
    pass


class BookingNotCancellableError(Exception):
    pass


class BookingCodeConflictError(Exception):
    pass


def _booking_code() -> str:
    return f"BK-{uuid4().hex[:12].upper()}"


def _map_rpc_error(error: APIError) -> Exception:
    text = " ".join(str(part) for part in error.args)
    message = str(getattr(error, "message", ""))
    combined = f"{message} {text}"
    mappings: tuple[tuple[str, type[Exception]], ...] = (
        ("SEAT_ALREADY_BOOKED", SeatAlreadyBookedError),
        ("SEAT_NOT_FOUND", BookingSeatNotFoundError),
        ("FLIGHT_NOT_FOUND", BookingFlightNotFoundError),
        ("FLIGHT_SEAT_MISMATCH", FlightSeatMismatchError),
        ("FLIGHT_NOT_BOOKABLE", FlightNotBookableError),
        ("BOOKING_NOT_FOUND", BookingNotFoundError),
        ("BOOKING_ACCESS_DENIED", BookingAccessDeniedError),
        ("BOOKING_ALREADY_CANCELLED", BookingAlreadyCancelledError),
        ("BOOKING_NOT_CANCELLABLE", BookingNotCancellableError),
        ("BOOKING_CODE_CONFLICT", BookingCodeConflictError),
    )
    for marker, exception_type in mappings:
        if marker in combined:
            return exception_type()
    return error


def _get_booking_row(client: Client, booking_id: UUID) -> dict[str, Any]:
    response = (
        client.table("bookings")
        .select(BOOKING_SELECT)
        .eq("id", str(booking_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise BookingNotFoundError
    return rows[0]


def get_booking(
    client: Client,
    booking_id: UUID,
    requester_user_id: UUID,
    is_admin: bool = False,
) -> BookingRead:
    """본인 또는 관리자에게만 예약 상세를 반환한다."""

    row = _get_booking_row(client, booking_id)
    if not is_admin and row["user_id"] != str(requester_user_id):
        raise BookingAccessDeniedError
    return BookingRead.model_validate(row)


def create_booking(
    client: Client,
    user_id: UUID,
    data: BookingCreate,
) -> BookingRead:
    """DB RPC로 좌석 잠금·예약·로그 생성을 원자적으로 처리한다."""

    response = None
    for attempt in range(3):
        try:
            response = client.rpc(
                "create_booking_atomic",
                {
                    "p_user_id": str(user_id),
                    "p_flight_id": str(data.flight_id),
                    "p_seat_id": str(data.seat_id),
                    "p_passenger_name": data.passenger_name,
                    "p_booking_code": _booking_code(),
                },
            ).execute()
            break
        except APIError as error:
            mapped = _map_rpc_error(error)
            if isinstance(mapped, BookingCodeConflictError) and attempt < 2:
                continue
            raise mapped from error

    if response is None:
        raise RuntimeError("예약번호 생성 재시도에 실패했습니다.")
    result = response.data
    if isinstance(result, list):
        result = result[0] if result else None
    if not result or not result.get("id"):
        raise RuntimeError("예약 생성 RPC 결과에 ID가 없습니다.")
    return get_booking(client, UUID(result["id"]), user_id)


def list_my_bookings(
    client: Client,
    user_id: UUID,
    status: BookingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> BookingPage:
    query = (
        client.table("bookings")
        .select(BOOKING_SELECT, count="exact")
        .eq("user_id", str(user_id))
    )
    if status is not None:
        query = query.eq("status", status.value)
    start = (page - 1) * page_size
    response = (
        query.order("created_at", desc=True)
        .range(start, start + page_size - 1)
        .execute()
    )
    total = response.count or 0
    return BookingPage(
        items=[BookingRead.model_validate(row) for row in response.data or []],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


def cancel_booking(
    client: Client,
    booking_id: UUID,
    user_id: UUID,
    data: BookingCancel,
) -> BookingRead:
    """DB RPC로 예약 취소·좌석 복원·로그 생성을 원자적으로 처리한다."""

    try:
        client.rpc(
            "cancel_booking_atomic",
            {
                "p_booking_id": str(booking_id),
                "p_user_id": str(user_id),
                "p_reason": data.reason,
            },
        ).execute()
    except APIError as error:
        raise _map_rpc_error(error) from error
    return get_booking(client, booking_id, user_id)


def list_admin_bookings(
    client: Client,
    status: BookingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> BookingPage:
    """관리자가 전체 사용자의 예약을 최신순으로 조회한다."""

    query = client.table("bookings").select(BOOKING_SELECT, count="exact")
    if status is not None:
        query = query.eq("status", status.value)
    start = (page - 1) * page_size
    response = (
        query.order("created_at", desc=True)
        .range(start, start + page_size - 1)
        .execute()
    )
    total = response.count or 0
    return BookingPage(
        items=[BookingRead.model_validate(row) for row in response.data or []],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


def update_booking_status(
    client: Client,
    booking_id: UUID,
    actor_user_id: UUID,
    data: BookingStatusUpdate,
) -> BookingRead:
    """관리자 상태 변경을 좌석·로그와 함께 원자적으로 처리한다."""

    try:
        client.rpc(
            "set_booking_status_atomic",
            {
                "p_booking_id": str(booking_id),
                "p_status": data.status.value,
                "p_actor_user_id": str(actor_user_id),
            },
        ).execute()
    except APIError as error:
        raise _map_rpc_error(error) from error
    return get_booking(
        client,
        booking_id,
        requester_user_id=actor_user_id,
        is_admin=True,
    )
