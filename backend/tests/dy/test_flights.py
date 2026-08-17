from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.dn.supabase_client import get_supabase
from app.routers.dy.flight_router import router
from app.schemas.dy.flight_schema import (
    AdminFlightFilter,
    CabinClass,
    FlightCreate,
    FlightSearchParams,
    FlightUpdate,
)
from app.services.dy.flight_service import (
    FLIGHT_SELECT,
    FlightConflictError,
    FlightInUseError,
    create_flight,
    delete_flight,
    get_flight,
    list_admin_flights,
    search_flights,
    update_flight,
)


FLIGHT_ID = "00000000-0000-0000-0000-00000000c001"
AIRPORT_ICN = {
    "id": "00000000-0000-0000-0000-00000000a001",
    "iata_code": "ICN",
    "name": "인천국제공항",
    "city": "인천",
    "country": "대한민국",
}
AIRPORT_CJU = {
    "id": "00000000-0000-0000-0000-00000000a003",
    "iata_code": "CJU",
    "name": "제주국제공항",
    "city": "제주",
    "country": "대한민국",
}


def flight_row(
    *,
    flight_id: str = FLIGHT_ID,
    departure_at: str = "2026-08-07T03:00:00",
    seats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": flight_id,
        "flight_number": "KE1201",
        "origin": AIRPORT_ICN,
        "destination": AIRPORT_CJU,
        "departure_at": departure_at,
        "arrival_at": "2026-08-07T04:10:00",
        "status": "SCHEDULED",
        "base_price": 89000,
        "seats": seats
        if seats is not None
        else [
            {"id": "seat-1", "cabin_class": "ECONOMY", "price": 99000, "status": "AVAILABLE"},
            {"id": "seat-2", "cabin_class": "ECONOMY", "price": 89000, "status": "AVAILABLE"},
            {"id": "seat-3", "cabin_class": "BUSINESS", "price": 159000, "status": "AVAILABLE"},
        ],
    }


@dataclass
class FakeResponse:
    data: list[dict[str, Any]] | None
    count: int | None = None


class FakeQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, Any]] = []

    def select(self, value: str, **kwargs: Any) -> "FakeQuery":
        self.calls.append(("select", (value, kwargs)))
        return self

    def eq(self, column: str, value: Any) -> "FakeQuery":
        self.calls.append(("eq", (column, value)))
        return self

    def gte(self, column: str, value: Any) -> "FakeQuery":
        self.calls.append(("gte", (column, value)))
        return self

    def lt(self, column: str, value: Any) -> "FakeQuery":
        self.calls.append(("lt", (column, value)))
        return self

    def in_(self, column: str, value: Any) -> "FakeQuery":
        self.calls.append(("in", (column, value)))
        return self

    def limit(self, value: int) -> "FakeQuery":
        self.calls.append(("limit", value))
        return self

    def ilike(self, column: str, value: Any) -> "FakeQuery":
        self.calls.append(("ilike", (column, value)))
        return self

    def order(self, column: str, **kwargs: Any) -> "FakeQuery":
        self.calls.append(("order", (column, kwargs)))
        return self

    def range(self, start: int, end: int) -> "FakeQuery":
        self.calls.append(("range", (start, end)))
        return self

    def execute(self) -> FakeResponse:
        return FakeResponse(self.rows, count=len(self.rows))


class FakeSupabase:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.query = FakeQuery(rows)
        self.table_name: str | None = None

    def table(self, name: str) -> FakeQuery:
        self.table_name = name
        return self.query


def create_client(fake: FakeSupabase) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase] = lambda: fake
    return TestClient(app)


def search_params(**overrides: Any) -> FlightSearchParams:
    values: dict[str, Any] = {
        "origin": "ICN",
        "destination": "CJU",
        "date": date(2026, 8, 7),
        "passengers": 1,
        "cabin_class": "ECONOMY",
    }
    values.update(overrides)
    return FlightSearchParams(**values)


def test_search_flights_uses_korean_date_as_utc_range() -> None:
    fake = FakeSupabase([flight_row()])

    result = search_flights(fake, search_params())  # type: ignore[arg-type]

    assert fake.table_name == "flights"
    assert ("select", (FLIGHT_SELECT, {})) in fake.query.calls
    assert ("gte", ("departure_at", "2026-08-06T15:00:00+00:00")) in fake.query.calls
    assert ("lt", ("departure_at", "2026-08-07T15:00:00+00:00")) in fake.query.calls
    assert result[0].lowest_seat_price == 89000
    assert result[0].available_seats == 2


def test_search_flights_excludes_flights_without_enough_seats() -> None:
    fake = FakeSupabase([flight_row()])

    result = search_flights(fake, search_params(passengers=3))  # type: ignore[arg-type]

    assert result == []


def test_search_flights_sorts_by_lowest_price() -> None:
    expensive = flight_row(
        flight_id="00000000-0000-0000-0000-00000000c002",
        seats=[{"id": "s1", "cabin_class": "ECONOMY", "price": 120000, "status": "AVAILABLE"}],
    )
    cheap = flight_row(
        flight_id="00000000-0000-0000-0000-00000000c003",
        seats=[{"id": "s2", "cabin_class": "ECONOMY", "price": 65000, "status": "AVAILABLE"}],
    )
    fake = FakeSupabase([expensive, cheap])

    result = search_flights(fake, search_params())  # type: ignore[arg-type]

    assert [flight.lowest_seat_price for flight in result] == [65000, 120000]


def test_get_flight_groups_available_seats_by_cabin() -> None:
    fake = FakeSupabase([flight_row()])

    result = get_flight(fake, FLIGHT_ID)  # type: ignore[arg-type]

    assert result.available_seats == 3
    assert result.seats_by_cabin_class[CabinClass.ECONOMY].available_seats == 2
    assert result.seats_by_cabin_class[CabinClass.BUSINESS].lowest_price == 159000


def test_admin_flight_list_supports_optional_filters_and_pagination() -> None:
    fake = FakeSupabase([flight_row(seats=[])])

    result = list_admin_flights(
        fake,  # type: ignore[arg-type]
        AdminFlightFilter(
            flight_number=" ke ",
            status="SCHEDULED",
            page=1,
            page_size=10,
        ),
    )

    assert result.total == 1
    assert result.items[0].available_seats == 0
    assert result.items[0].lowest_seat_price == 89000
    assert ("ilike", ("flight_number", "%KE%")) in fake.query.calls
    assert ("eq", ("status", "SCHEDULED")) in fake.query.calls
    assert ("range", (0, 9)) in fake.query.calls


def test_search_route_returns_common_response() -> None:
    client = create_client(FakeSupabase([flight_row()]))

    response = client.get(
        "/flights",
        params={
            "origin": "ICN",
            "destination": "CJU",
            "date": "2026-08-07",
            "passengers": 1,
            "cabin_class": "ECONOMY",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["flight_number"] == "KE1201"
    assert response.json()["data"][0]["departure_at"] == "2026-08-07T03:00:00Z"


def test_search_route_rejects_same_origin_and_destination() -> None:
    client = create_client(FakeSupabase([]))

    response = client.get(
        "/flights",
        params={
            "origin": "ICN",
            "destination": "ICN",
            "date": "2026-08-07",
            "passengers": 1,
            "cabin_class": "ECONOMY",
        },
    )

    assert response.status_code == 422


def test_get_flight_route_returns_404_common_response() -> None:
    client = create_client(FakeSupabase([]))

    response = client.get(f"/flights/{FLIGHT_ID}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "FLIGHT_NOT_FOUND"


class ScriptedQuery:
    def __init__(
        self,
        table: str,
        response_rows: list[dict[str, Any]],
        calls: list[tuple[str, str, Any]],
    ) -> None:
        self.table = table
        self.response_rows = response_rows
        self.calls = calls

    def _chain(self, method: str, value: Any = None) -> "ScriptedQuery":
        self.calls.append((self.table, method, value))
        return self

    def select(self, value: str) -> "ScriptedQuery":
        return self._chain("select", value)

    def eq(self, column: str, value: Any) -> "ScriptedQuery":
        return self._chain("eq", (column, value))

    def neq(self, column: str, value: Any) -> "ScriptedQuery":
        return self._chain("neq", (column, value))

    def limit(self, value: int) -> "ScriptedQuery":
        return self._chain("limit", value)

    def insert(self, value: Any) -> "ScriptedQuery":
        return self._chain("insert", value)

    def update(self, value: Any) -> "ScriptedQuery":
        return self._chain("update", value)

    def delete(self) -> "ScriptedQuery":
        return self._chain("delete")

    def execute(self) -> FakeResponse:
        self.calls.append((self.table, "execute", None))
        return FakeResponse(self.response_rows)


class ScriptedSupabase:
    def __init__(self, responses: dict[str, list[list[dict[str, Any]]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> ScriptedQuery:
        queues = self.responses.get(name)
        if not queues:
            raise AssertionError(f"{name} 테이블의 가짜 응답이 부족합니다.")
        return ScriptedQuery(name, queues.pop(0), self.calls)


def mutation_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": FLIGHT_ID,
        "flight_number": "KE1201",
        "origin_airport_id": AIRPORT_ICN["id"],
        "destination_airport_id": AIRPORT_CJU["id"],
        "departure_at": "2026-08-07T03:00:00",
        "arrival_at": "2026-08-07T04:10:00",
        "status": "SCHEDULED",
        "base_price": 89000,
    }
    row.update(overrides)
    return row


def create_payload() -> FlightCreate:
    return FlightCreate(
        flight_number="KE1201",
        origin_airport_id=AIRPORT_ICN["id"],
        destination_airport_id=AIRPORT_CJU["id"],
        departure_at="2026-08-07T12:00:00+09:00",
        arrival_at="2026-08-07T13:10:00+09:00",
        base_price=89000,
    )


def test_flight_create_requires_timezone_and_valid_route() -> None:
    with pytest.raises(ValidationError):
        FlightCreate(
            flight_number="KE1201",
            origin_airport_id=AIRPORT_ICN["id"],
            destination_airport_id=AIRPORT_ICN["id"],
            departure_at=datetime(2026, 8, 7, 3),
            arrival_at=datetime(2026, 8, 7, 4),
            base_price=89000,
        )


def test_flight_update_rejects_empty_or_null_fields() -> None:
    with pytest.raises(ValidationError):
        FlightUpdate()
    with pytest.raises(ValidationError):
        FlightUpdate(status=None)


def test_create_flight_stores_utc_and_returns_detail() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [
                [],
                [{"id": FLIGHT_ID}],
                [flight_row()],
            ]
        }
    )

    result = create_flight(fake, create_payload())  # type: ignore[arg-type]

    insert_call = next(call for call in fake.calls if call[1] == "insert")
    assert insert_call[2]["departure_at"] == "2026-08-07T03:00:00"
    assert insert_call[2]["arrival_at"] == "2026-08-07T04:10:00"
    assert result.id == UUID(FLIGHT_ID)


def test_create_flight_rejects_duplicate_schedule() -> None:
    fake = ScriptedSupabase({"flights": [[{"id": FLIGHT_ID}]]})

    with pytest.raises(FlightConflictError):
        create_flight(fake, create_payload())  # type: ignore[arg-type]

    assert not any(call[1] == "insert" for call in fake.calls)


def test_update_flight_status_creates_event_log() -> None:
    updated_detail = flight_row()
    updated_detail["status"] = "DELAYED"
    fake = ScriptedSupabase(
        {
            "flights": [
                [mutation_row()],
                [],
                [mutation_row(status="DELAYED")],
                [updated_detail],
            ],
            "event_logs": [[{"id": 1}]],
        }
    )
    actor_id = UUID("00000000-0000-0000-0000-00000000b001")

    result = update_flight(
        fake,  # type: ignore[arg-type]
        UUID(FLIGHT_ID),
        FlightUpdate(status="DELAYED"),
        actor_user_id=actor_id,
    )

    event_insert = next(
        call for call in fake.calls if call[0] == "event_logs" and call[1] == "insert"
    )
    assert event_insert[2]["payload"] == {
        "previous_status": "SCHEDULED",
        "status": "DELAYED",
    }
    assert event_insert[2]["actor_user_id"] == str(actor_id)
    assert result.status == "DELAYED"


def test_delete_flight_rejects_linked_booking() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [[mutation_row()]],
            "bookings": [[{"id": "booking-1"}]],
        }
    )

    with pytest.raises(FlightInUseError):
        delete_flight(fake, UUID(FLIGHT_ID))  # type: ignore[arg-type]

    assert not any(call[1] == "delete" for call in fake.calls)


def test_delete_flight_without_relations() -> None:
    fake = ScriptedSupabase(
        {
            "flights": [[mutation_row()], []],
            "bookings": [[]],
            "seats": [[]],
        }
    )

    delete_flight(fake, UUID(FLIGHT_ID))  # type: ignore[arg-type]

    assert ("flights", "delete", None) in fake.calls
