from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from postgrest.exceptions import APIError

from app.schemas.dy.booking_schema import (
    BookingCancel,
    BookingCreate,
    BookingStatus,
    BookingStatusUpdate,
)
from app.services.dy.booking_service import (
    BookingAccessDeniedError,
    SeatAlreadyBookedError,
    cancel_booking,
    create_booking,
    get_booking,
    list_admin_bookings,
    list_my_bookings,
    update_booking_status,
)


BOOKING_ID = UUID("00000000-0000-0000-0000-00000000e001")
USER_ID = UUID("00000000-0000-0000-0000-00000000b002")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-00000000b003")
FLIGHT_ID = UUID("00000000-0000-0000-0000-00000000c001")
SEAT_ID = UUID("00000000-0000-0000-0000-00000000d004")


def booking_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": str(BOOKING_ID),
        "booking_code": "BK-TEST00000001",
        "user_id": str(USER_ID),
        "passenger_name": "테스트유저",
        "status": "CONFIRMED",
        "total_price": 89000,
        "created_at": "2026-08-07T03:00:00",
        "cancelled_at": None,
        "flight": {
            "id": str(FLIGHT_ID),
            "flight_number": "KE1201",
            "origin": {
                "id": "00000000-0000-0000-0000-00000000a001",
                "iata_code": "ICN",
                "name": "인천국제공항",
                "city": "인천",
                "country": "대한민국",
            },
            "destination": {
                "id": "00000000-0000-0000-0000-00000000a003",
                "iata_code": "CJU",
                "name": "제주국제공항",
                "city": "제주",
                "country": "대한민국",
            },
            "departure_at": "2026-08-15T03:00:00",
            "arrival_at": "2026-08-15T04:10:00",
            "status": "SCHEDULED",
        },
        "seat": {
            "id": str(SEAT_ID),
            "flight_id": str(FLIGHT_ID),
            "seat_number": "13A",
            "cabin_class": "ECONOMY",
            "price": 89000,
            "status": "BOOKED",
        },
    }
    row.update(overrides)
    return row


@dataclass
class FakeResponse:
    data: Any
    count: int | None = None


class FakeOperation:
    def __init__(self, response: FakeResponse | Exception, calls: list, name: str) -> None:
        self.response = response
        self.calls = calls
        self.name = name

    def _chain(self, method: str, value: Any = None):
        self.calls.append((self.name, method, value))
        return self

    def select(self, value, **kwargs): return self._chain("select", (value, kwargs))
    def eq(self, column, value): return self._chain("eq", (column, value))
    def limit(self, value): return self._chain("limit", value)
    def order(self, column, **kwargs): return self._chain("order", (column, kwargs))
    def range(self, start, end): return self._chain("range", (start, end))
    def execute(self):
        self.calls.append((self.name, "execute", None))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeSupabase:
    def __init__(
        self,
        *,
        tables: dict[str, list[FakeResponse | Exception]] | None = None,
        rpcs: dict[str, list[FakeResponse | Exception]] | None = None,
    ) -> None:
        self.tables = tables or {}
        self.rpcs = rpcs or {}
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> FakeOperation:
        if not self.tables.get(name):
            raise AssertionError(f"{name} 테이블 응답이 부족합니다.")
        return FakeOperation(self.tables[name].pop(0), self.calls, name)

    def rpc(self, name: str, params: dict[str, Any]) -> FakeOperation:
        self.calls.append((name, "rpc", params))
        if not self.rpcs.get(name):
            raise AssertionError(f"{name} RPC 응답이 부족합니다.")
        return FakeOperation(self.rpcs[name].pop(0), self.calls, name)


def test_create_booking_calls_atomic_rpc_and_returns_detail() -> None:
    fake = FakeSupabase(
        rpcs={"create_booking_atomic": [FakeResponse({"id": str(BOOKING_ID)})]},
        tables={"bookings": [FakeResponse([booking_row()])]},
    )

    result = create_booking(
        fake,  # type: ignore[arg-type]
        USER_ID,
        BookingCreate(
            flight_id=FLIGHT_ID,
            seat_id=SEAT_ID,
            passenger_name="  테스트유저  ",
        ),
    )

    rpc_params = next(call[2] for call in fake.calls if call[:2] == ("create_booking_atomic", "rpc"))
    assert rpc_params["p_passenger_name"] == "테스트유저"
    assert rpc_params["p_booking_code"].startswith("BK-")
    assert result.id == BOOKING_ID


def test_create_booking_maps_concurrent_seat_conflict() -> None:
    api_error = APIError(
        {"message": "SEAT_ALREADY_BOOKED", "code": "P0001", "hint": "", "details": ""}
    )
    fake = FakeSupabase(
        rpcs={"create_booking_atomic": [api_error]},
    )

    with pytest.raises(SeatAlreadyBookedError):
        create_booking(
            fake,  # type: ignore[arg-type]
            USER_ID,
            BookingCreate(
                flight_id=FLIGHT_ID,
                seat_id=SEAT_ID,
                passenger_name="테스트유저",
            ),
        )


def test_get_booking_enforces_owner() -> None:
    fake = FakeSupabase(tables={"bookings": [FakeResponse([booking_row()])]})

    with pytest.raises(BookingAccessDeniedError):
        get_booking(fake, BOOKING_ID, OTHER_USER_ID)  # type: ignore[arg-type]


def test_admin_can_read_other_users_booking() -> None:
    fake = FakeSupabase(tables={"bookings": [FakeResponse([booking_row()])]})

    result = get_booking(
        fake,  # type: ignore[arg-type]
        BOOKING_ID,
        OTHER_USER_ID,
        is_admin=True,
    )

    assert result.user_id == USER_ID


def test_list_my_bookings_filters_and_paginates() -> None:
    fake = FakeSupabase(
        tables={"bookings": [FakeResponse([booking_row()], count=21)]}
    )

    result = list_my_bookings(
        fake,  # type: ignore[arg-type]
        USER_ID,
        status=BookingStatus.CONFIRMED,
        page=2,
        page_size=10,
    )

    assert result.total == 21
    assert result.total_pages == 3
    assert ("bookings", "eq", ("status", "CONFIRMED")) in fake.calls
    assert ("bookings", "range", (10, 19)) in fake.calls


def test_cancel_booking_calls_atomic_rpc_then_returns_cancelled_detail() -> None:
    cancelled = booking_row(
        status="CANCELLED",
        cancelled_at="2026-08-08T03:00:00",
    )
    cancelled["seat"] = {**cancelled["seat"], "status": "AVAILABLE"}
    fake = FakeSupabase(
        rpcs={"cancel_booking_atomic": [FakeResponse({"id": str(BOOKING_ID)})]},
        tables={"bookings": [FakeResponse([cancelled])]},
    )

    result = cancel_booking(
        fake,  # type: ignore[arg-type]
        BOOKING_ID,
        USER_ID,
        BookingCancel(reason="일정 변경"),
    )

    rpc_params = next(call[2] for call in fake.calls if call[:2] == ("cancel_booking_atomic", "rpc"))
    assert rpc_params["p_reason"] == "일정 변경"
    assert result.status is BookingStatus.CANCELLED
    assert result.seat.status == "AVAILABLE"


def test_booking_rpc_contains_concurrency_and_event_guards() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    rpc_sql = (repo_root / "backend/sql/dy/booking_rpcs.sql").read_text(
        encoding="utf-8"
    )
    schema_sql = (repo_root / "backend/sql/dn/schema.sql").read_text(
        encoding="utf-8"
    )

    assert "for update" in rpc_sql.lower()
    assert "create_booking_atomic" in rpc_sql
    assert "cancel_booking_atomic" in rpc_sql
    assert "set_booking_status_atomic" in rpc_sql
    assert "insert into public.event_logs" in rpc_sql.lower()
    assert "ux_bookings_active_seat" in schema_sql


def test_admin_booking_list_is_not_scoped_to_one_user() -> None:
    fake = FakeSupabase(
        tables={"bookings": [FakeResponse([booking_row()], count=1)]}
    )

    result = list_admin_bookings(
        fake,  # type: ignore[arg-type]
        status=BookingStatus.CONFIRMED,
    )

    assert result.total == 1
    assert ("bookings", "eq", ("status", "CONFIRMED")) in fake.calls
    assert not any(
        call[:2] == ("bookings", "eq") and call[2][0] == "user_id"
        for call in fake.calls
    )


def test_admin_booking_status_uses_atomic_rpc() -> None:
    cancelled = booking_row(
        status="CANCELLED",
        cancelled_at="2026-08-08T03:00:00",
    )
    cancelled["seat"] = {**cancelled["seat"], "status": "AVAILABLE"}
    fake = FakeSupabase(
        rpcs={"set_booking_status_atomic": [FakeResponse({"id": str(BOOKING_ID)})]},
        tables={"bookings": [FakeResponse([cancelled])]},
    )
    admin_id = UUID("00000000-0000-0000-0000-00000000b001")

    result = update_booking_status(
        fake,  # type: ignore[arg-type]
        BOOKING_ID,
        admin_id,
        BookingStatusUpdate(status="CANCELLED"),
    )

    params = next(
        call[2] for call in fake.calls if call[:2] == ("set_booking_status_atomic", "rpc")
    )
    assert params == {
        "p_booking_id": str(BOOKING_ID),
        "p_status": "CANCELLED",
        "p_actor_user_id": str(admin_id),
    }
    assert result.status is BookingStatus.CANCELLED
