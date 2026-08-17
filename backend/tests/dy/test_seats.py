from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.routers.dy.seat_router import router
from app.schemas.dy.flight_schema import CabinClass
from app.schemas.dy.seat_schema import SeatCreate, SeatStatus, SeatUpdate
from app.services.dy.seat_service import (
    SeatAlreadyExistsError,
    SeatInUseError,
    create_seat,
    delete_seat,
    list_seats,
    update_seat,
)


FLIGHT_ID = UUID("00000000-0000-0000-0000-00000000c001")
SEAT_ID = UUID("00000000-0000-0000-0000-00000000d001")
ADMIN_ID = UUID("00000000-0000-0000-0000-00000000b001")


def seat_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": str(SEAT_ID),
        "flight_id": str(FLIGHT_ID),
        "seat_number": "12A",
        "cabin_class": "ECONOMY",
        "price": 89000,
        "status": "AVAILABLE",
    }
    row.update(overrides)
    return row


@dataclass
class FakeResponse:
    data: list[dict[str, Any]] | None


class ScriptedQuery:
    def __init__(self, table: str, rows: list[dict[str, Any]], calls: list) -> None:
        self.table = table
        self.rows = rows
        self.calls = calls

    def _chain(self, name: str, value: Any = None):
        self.calls.append((self.table, name, value))
        return self

    def select(self, value): return self._chain("select", value)
    def eq(self, column, value): return self._chain("eq", (column, value))
    def neq(self, column, value): return self._chain("neq", (column, value))
    def limit(self, value): return self._chain("limit", value)
    def insert(self, value): return self._chain("insert", value)
    def update(self, value): return self._chain("update", value)
    def delete(self): return self._chain("delete")
    def execute(self):
        self.calls.append((self.table, "execute", None))
        return FakeResponse(self.rows)


class ScriptedSupabase:
    def __init__(self, responses: dict[str, list[list[dict[str, Any]]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> ScriptedQuery:
        if not self.responses.get(name):
            raise AssertionError(f"{name} 가짜 응답이 부족합니다.")
        return ScriptedQuery(name, self.responses[name].pop(0), self.calls)


def test_list_seats_filters_and_uses_natural_order() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [[{"id": str(FLIGHT_ID)}]],
            "seats": [[seat_row(seat_number="12A"), seat_row(id="00000000-0000-0000-0000-00000000d002", seat_number="2A")]],
        }
    )

    result = list_seats(fake, FLIGHT_ID, CabinClass.ECONOMY)  # type: ignore[arg-type]

    assert [seat.seat_number for seat in result] == ["2A", "12A"]
    assert ("seats", "eq", ("cabin_class", "ECONOMY")) in fake.calls


def test_create_seat_rejects_duplicate_number() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [[{"id": str(FLIGHT_ID)}]],
            "seats": [[{"id": str(SEAT_ID)}]],
        }
    )

    with pytest.raises(SeatAlreadyExistsError):
        create_seat(
            fake,  # type: ignore[arg-type]
            FLIGHT_ID,
            SeatCreate(seat_number="12A", cabin_class="ECONOMY", price=89000),
            ADMIN_ID,
        )


def test_create_seat_logs_event() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [[{"id": str(FLIGHT_ID)}]],
            "seats": [[], [seat_row()]],
            "event_logs": [[{"id": 1}]],
        }
    )

    result = create_seat(
        fake,  # type: ignore[arg-type]
        FLIGHT_ID,
        SeatCreate(seat_number="12A", cabin_class="ECONOMY", price=89000),
        ADMIN_ID,
    )

    event = next(call[2] for call in fake.calls if call[:2] == ("event_logs", "insert"))
    assert event["payload"]["action"] == "CREATED"
    assert result.seat_number == "12A"


def test_update_booked_seat_is_blocked() -> None:
    fake = ScriptedSupabase({"seats": [[seat_row(status="BOOKED")]]})

    with pytest.raises(SeatInUseError):
        update_seat(
            fake,  # type: ignore[arg-type]
            SEAT_ID,
            SeatUpdate(price=99000),
            ADMIN_ID,
        )


def test_update_seat_logs_previous_and_current_values() -> None:
    fake = ScriptedSupabase(
        {
            "seats": [[seat_row()], [seat_row(price=99000)]],
            "event_logs": [[{"id": 1}]],
        }
    )

    updated = update_seat(
        fake,  # type: ignore[arg-type]
        SEAT_ID,
        SeatUpdate(price=99000),
        ADMIN_ID,
    )

    event = next(call[2] for call in fake.calls if call[:2] == ("event_logs", "insert"))
    assert event["payload"]["changes"]["price"] == {"previous": 89000, "current": 99000}
    assert updated.price == 99000


def test_update_seat_status_log_uses_json_strings() -> None:
    fake = ScriptedSupabase(
        {
            "seats": [[seat_row()], [seat_row(status="HELD")]],
            "event_logs": [[{"id": 1}]],
        }
    )

    update_seat(
        fake,  # type: ignore[arg-type]
        SEAT_ID,
        SeatUpdate(status="HELD"),
        ADMIN_ID,
    )

    event = next(call[2] for call in fake.calls if call[:2] == ("event_logs", "insert"))
    assert event["payload"]["changes"]["status"] == {
        "previous": "AVAILABLE",
        "current": "HELD",
    }


def test_delete_seat_with_booking_history_is_blocked() -> None:
    fake = ScriptedSupabase(
        {
            "seats": [[seat_row()]],
            "bookings": [[{"id": "booking-1"}]],
        }
    )

    with pytest.raises(SeatInUseError):
        delete_seat(fake, SEAT_ID, ADMIN_ID)  # type: ignore[arg-type]


def test_list_seats_route_returns_404_for_missing_flight() -> None:
    fake = ScriptedSupabase({"flights": [[]]})
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase] = lambda: fake
    client = TestClient(app)

    response = client.get(f"/flights/{FLIGHT_ID}/seats")

    assert response.status_code == 404
    assert response.json()["error_code"] == "FLIGHT_NOT_FOUND"


def test_list_seats_route_returns_common_response() -> None:
    fake = ScriptedSupabase(
        {"flights": [[{"id": str(FLIGHT_ID)}]], "seats": [[seat_row()]]}
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase] = lambda: fake
    client = TestClient(app)

    response = client.get(
        f"/flights/{FLIGHT_ID}/seats", params={"cabin_class": "ECONOMY"}
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["seat_number"] == "12A"
