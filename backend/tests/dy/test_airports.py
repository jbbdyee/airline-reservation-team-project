from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.routers.dy.airport_router import router
from app.services.dy.airport_service import AIRPORT_COLUMNS, list_airports


AIRPORT_ROWS = [
    {
        "id": "00000000-0000-0000-0000-00000000a003",
        "iata_code": "CJU",
        "name": "제주국제공항",
        "city": "제주",
        "country": "대한민국",
    },
    {
        "id": "00000000-0000-0000-0000-00000000a001",
        "iata_code": "ICN",
        "name": "인천국제공항",
        "city": "인천",
        "country": "대한민국",
    },
]


@dataclass
class FakeResponse:
    data: list[dict[str, Any]] | None


class FakeAirportQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.selected_columns: str | None = None
        self.or_expression: str | None = None
        self.order_column: str | None = None

    def select(self, columns: str) -> "FakeAirportQuery":
        self.selected_columns = columns
        return self

    def or_(self, expression: str) -> "FakeAirportQuery":
        self.or_expression = expression
        return self

    def order(self, column: str) -> "FakeAirportQuery":
        self.order_column = column
        return self

    def execute(self) -> FakeResponse:
        return FakeResponse(data=self.rows)


class FakeSupabase:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.query = FakeAirportQuery(rows)
        self.table_name: str | None = None

    def table(self, name: str) -> FakeAirportQuery:
        self.table_name = name
        return self.query


def create_test_client(fake_supabase: FakeSupabase) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase] = lambda: fake_supabase
    return TestClient(app)


def test_list_airports_service_builds_sorted_query() -> None:
    fake = FakeSupabase(AIRPORT_ROWS)

    result = list_airports(fake)  # type: ignore[arg-type]

    assert fake.table_name == "airports"
    assert fake.query.selected_columns == AIRPORT_COLUMNS
    assert fake.query.order_column == "iata_code"
    assert fake.query.or_expression is None
    assert [airport.iata_code for airport in result] == ["CJU", "ICN"]


def test_list_airports_service_filters_code_name_and_city() -> None:
    fake = FakeSupabase([AIRPORT_ROWS[1]])

    list_airports(fake, keyword=" 인천 ")  # type: ignore[arg-type]

    assert fake.query.or_expression == (
        "iata_code.ilike.%인천%,name.ilike.%인천%,city.ilike.%인천%"
    )


def test_list_airports_route_returns_common_response() -> None:
    client = create_test_client(FakeSupabase(AIRPORT_ROWS))

    response = client.get("/airports")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error_code"] is None
    assert body["message"] == "공항 목록을 조회했습니다."
    assert body["data"][0]["iata_code"] == "CJU"


def test_list_airports_route_returns_empty_list() -> None:
    client = create_test_client(FakeSupabase([]))

    response = client.get("/airports", params={"keyword": "없는공항"})

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_airports_route_rejects_filter_injection_characters() -> None:
    client = create_test_client(FakeSupabase(AIRPORT_ROWS))

    response = client.get("/airports", params={"keyword": "ICN,city.eq.서울"})

    assert response.status_code == 422


def test_list_airports_route_rejects_blank_keyword() -> None:
    client = create_test_client(FakeSupabase(AIRPORT_ROWS))

    response = client.get("/airports", params={"keyword": "   "})

    assert response.status_code == 422
