"""좌석 조회·관리 비즈니스 로직."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from supabase import Client

from app.schemas.dy.flight_schema import CabinClass
from app.schemas.dy.seat_schema import SeatCreate, SeatRead, SeatStatus, SeatUpdate


SEAT_COLUMNS = "id,flight_id,seat_number,cabin_class,price,status"


class SeatNotFoundError(Exception):
    """요청한 좌석이 없을 때 발생한다."""


class SeatAlreadyExistsError(Exception):
    """항공편에 같은 좌석 번호가 이미 있을 때 발생한다."""


class SeatInUseError(Exception):
    """예약과 연결된 좌석을 변경·삭제하려 할 때 발생한다."""


class SeatFlightNotFoundError(Exception):
    """좌석이 속할 항공편이 없을 때 발생한다."""


def _flight_exists(client: Client, flight_id: UUID) -> bool:
    response = (
        client.table("flights")
        .select("id")
        .eq("id", str(flight_id))
        .limit(1)
        .execute()
    )
    return bool(response.data)


def _natural_seat_key(seat: SeatRead) -> tuple[int, str]:
    match = re.fullmatch(r"([0-9]+)([A-Z])", seat.seat_number)
    if match is None:
        return (10_000, seat.seat_number)
    return (int(match.group(1)), match.group(2))


def list_seats(
    client: Client,
    flight_id: UUID,
    cabin_class: CabinClass | None = None,
) -> list[SeatRead]:
    """항공편의 좌석을 좌석 번호 자연순으로 반환한다."""

    if not _flight_exists(client, flight_id):
        raise SeatFlightNotFoundError

    query = (
        client.table("seats")
        .select(SEAT_COLUMNS)
        .eq("flight_id", str(flight_id))
    )
    if cabin_class is not None:
        query = query.eq("cabin_class", cabin_class.value)
    response = query.execute()
    seats = [SeatRead.model_validate(row) for row in response.data or []]
    return sorted(seats, key=_natural_seat_key)


def get_seat(client: Client, seat_id: UUID) -> SeatRead:
    response = (
        client.table("seats")
        .select(SEAT_COLUMNS)
        .eq("id", str(seat_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise SeatNotFoundError
    return SeatRead.model_validate(rows[0])


def _seat_number_exists(
    client: Client,
    flight_id: UUID,
    seat_number: str,
    exclude_seat_id: UUID | None = None,
) -> bool:
    query = (
        client.table("seats")
        .select("id")
        .eq("flight_id", str(flight_id))
        .eq("seat_number", seat_number)
    )
    if exclude_seat_id is not None:
        query = query.neq("id", str(exclude_seat_id))
    return bool(query.limit(1).execute().data)


def _log_seat_change(
    client: Client,
    seat_id: UUID,
    flight_id: UUID,
    actor_user_id: UUID,
    payload: dict[str, Any],
) -> None:
    client.table("event_logs").insert(
        {
            "event_type": "SEAT_CHANGED",
            "resource_id": str(seat_id),
            "flight_id": str(flight_id),
            "booking_id": None,
            "actor_user_id": str(actor_user_id),
            "payload": payload,
        }
    ).execute()


def _json_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def create_seat(
    client: Client,
    flight_id: UUID,
    data: SeatCreate,
    actor_user_id: UUID,
) -> SeatRead:
    """관리자가 항공편에 좌석을 생성한다."""

    if not _flight_exists(client, flight_id):
        raise SeatFlightNotFoundError
    if _seat_number_exists(client, flight_id, data.seat_number):
        raise SeatAlreadyExistsError

    payload = data.model_dump(mode="json")
    payload["flight_id"] = str(flight_id)
    response = client.table("seats").insert(payload).execute()
    rows = response.data or []
    if not rows:
        raise RuntimeError("좌석 생성 결과가 없습니다.")
    seat = SeatRead.model_validate(rows[0])
    _log_seat_change(
        client,
        seat.id,
        flight_id,
        actor_user_id,
        {
            "action": "CREATED",
            "seat_number": seat.seat_number,
            "status": seat.status.value,
        },
    )
    return seat


def update_seat(
    client: Client,
    seat_id: UUID,
    data: SeatUpdate,
    actor_user_id: UUID,
) -> SeatRead:
    """예약되지 않은 좌석을 부분 수정한다."""

    current = get_seat(client, seat_id)
    if current.status is SeatStatus.BOOKED:
        raise SeatInUseError

    changes = data.model_dump(exclude_unset=True, mode="json")
    new_number = changes.get("seat_number")
    if new_number is not None and new_number != current.seat_number:
        if _seat_number_exists(client, current.flight_id, new_number, seat_id):
            raise SeatAlreadyExistsError

    response = (
        client.table("seats")
        .update(changes)
        .eq("id", str(seat_id))
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise SeatNotFoundError
    updated = SeatRead.model_validate(rows[0])
    _log_seat_change(
        client,
        seat_id,
        current.flight_id,
        actor_user_id,
        {
            "action": "UPDATED",
            "changes": {
                field: {
                    "previous": _json_value(getattr(current, field)),
                    "current": _json_value(getattr(updated, field)),
                }
                for field in changes
            },
        },
    )
    return updated


def delete_seat(client: Client, seat_id: UUID, actor_user_id: UUID) -> None:
    """예약 이력이 없는 좌석을 삭제한다."""

    current = get_seat(client, seat_id)
    booking_response = (
        client.table("bookings")
        .select("id")
        .eq("seat_id", str(seat_id))
        .limit(1)
        .execute()
    )
    if current.status is SeatStatus.BOOKED or booking_response.data:
        raise SeatInUseError

    client.table("seats").delete().eq("id", str(seat_id)).execute()
    _log_seat_change(
        client,
        seat_id,
        current.flight_id,
        actor_user_id,
        {
            "action": "DELETED",
            "seat_number": current.seat_number,
            "status": current.status.value,
        },
    )
