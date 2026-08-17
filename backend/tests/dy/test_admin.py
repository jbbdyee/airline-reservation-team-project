from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.dy.admin_schema import DashboardFilter
from app.services.dy.admin_service import get_admin_dashboard


def event_row() -> dict[str, Any]:
    return {
        "id": 1,
        "event_type": "BOOKING_CHANGED",
        "resource_id": "00000000-0000-0000-0000-00000000e001",
        "flight_id": "00000000-0000-0000-0000-00000000c001",
        "booking_id": "00000000-0000-0000-0000-00000000e001",
        "actor_user_id": "00000000-0000-0000-0000-00000000b002",
        "payload": {"status": "CONFIRMED"},
        "created_at": "2026-08-07T03:00:00",
    }


@dataclass
class FakeResponse:
    data: Any


class FakeQuery:
    def __init__(self, table: str, response: FakeResponse, calls: list) -> None:
        self.table = table
        self.response = response
        self.calls = calls

    def _chain(self, method: str, value: Any = None):
        self.calls.append((self.table, method, value))
        return self

    def select(self, value): return self._chain("select", value)
    def eq(self, column, value): return self._chain("eq", (column, value))
    def gte(self, column, value): return self._chain("gte", (column, value))
    def lte(self, column, value): return self._chain("lte", (column, value))
    def order(self, column, **kwargs): return self._chain("order", (column, kwargs))
    def limit(self, value): return self._chain("limit", value)
    def execute(self): return self.response


class FakeSupabase:
    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> FakeQuery:
        if not self.responses.get(name):
            raise AssertionError(f"{name} 가짜 응답이 부족합니다.")
        return FakeQuery(name, self.responses[name].pop(0), self.calls)


def test_admin_dashboard_combines_operating_and_quality_metrics() -> None:
    fake = FakeSupabase(
        {
            "flights": [
                FakeResponse(
                    [
                        {"status": "SCHEDULED"},
                        {"status": "DELAYED"},
                        {"status": "CANCELLED"},
                    ]
                )
            ],
            "bookings": [
                FakeResponse(
                    [
                        {"status": "CONFIRMED", "total_price": 89000, "created_at": "2026-08-07"},
                        {"status": "CONFIRMED", "total_price": 65000, "created_at": "2026-08-07"},
                        {"status": "CANCELLED", "total_price": 55000, "created_at": "2026-08-07"},
                    ]
                )
            ],
            "feedbacks": [
                FakeResponse([{"rating": 1}, {"rating": 2}, {"rating": 5}])
            ],
            "event_logs": [FakeResponse([event_row()])],
        }
    )

    result = get_admin_dashboard(fake, DashboardFilter())  # type: ignore[arg-type]

    assert result.flights.total == 3
    assert result.flights.delayed == 1
    assert result.bookings.total == 3
    assert result.bookings.confirmed_revenue == 154000
    assert result.chat_feedbacks.average_rating == 2.67
    assert result.chat_feedbacks.low_rating_ratio == 0.6667
    assert result.recent_events[0].id == 1


def test_admin_dashboard_applies_period_to_time_based_metrics() -> None:
    fake = FakeSupabase(
        {
            "flights": [FakeResponse([])],
            "bookings": [FakeResponse([])],
            "feedbacks": [FakeResponse([])],
            "event_logs": [FakeResponse([])],
        }
    )
    filters = DashboardFilter(
        start_at="2026-08-07T00:00:00+09:00",
        end_at="2026-08-08T00:00:00+09:00",
    )

    result = get_admin_dashboard(fake, filters)  # type: ignore[arg-type]

    assert result.bookings.total == 0
    assert result.chat_feedbacks.average_rating is None
    # 예약, 피드백, 이벤트 세 쿼리 모두 같은 UTC 기간을 적용한다.
    assert fake.calls.count(("bookings", "gte", ("created_at", "2026-08-06T15:00:00"))) == 1
    assert fake.calls.count(("feedbacks", "gte", ("created_at", "2026-08-06T15:00:00"))) == 1
    assert fake.calls.count(("event_logs", "gte", ("created_at", "2026-08-06T15:00:00"))) == 1
