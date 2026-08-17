from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.routers.dy import admin_router
from app.schemas.dy.admin_schema import (
    AdminDashboardRead,
    BookingMetrics,
    FlightMetrics,
)
from app.schemas.dy.feedback_schema import ChatFeedbackSummary
from app.schemas.dy.flight_schema import FlightPage
from app.services.dy.flight_service import FlightConflictError, FlightInUseError
from app.services.dy.seat_service import SeatInUseError


ADMIN_ID = "00000000-0000-0000-0000-00000000b001"
FLIGHT_ID = "00000000-0000-0000-0000-00000000c001"
SEAT_ID = "00000000-0000-0000-0000-00000000d001"


def allowed_admin():
    return {"id": ADMIN_ID, "role": "ADMIN"}


def denied_admin():
    raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def create_client(dependency=allowed_admin) -> TestClient:
    app = FastAPI()
    app.include_router(admin_router.build_admin_router(dependency))
    app.dependency_overrides[get_supabase] = lambda: object()
    return TestClient(app)


def flight_create_body() -> dict:
    return {
        "flight_number": "KE1201",
        "origin_airport_id": "00000000-0000-0000-0000-00000000a001",
        "destination_airport_id": "00000000-0000-0000-0000-00000000a003",
        "departure_at": "2026-08-15T03:00:00Z",
        "arrival_at": "2026-08-15T04:10:00Z",
        "base_price": 89000,
    }


def test_all_admin_resource_routes_require_admin() -> None:
    client = create_client(denied_admin)
    requests = [
        client.get("/admin/dashboard"),
        client.get("/admin/flights"),
        client.post("/flights", json=flight_create_body()),
        client.put(f"/flights/{FLIGHT_ID}", json={"status": "DELAYED"}),
        client.delete(f"/flights/{FLIGHT_ID}"),
        client.post(
            f"/flights/{FLIGHT_ID}/seats",
            json={"seat_number": "12A", "cabin_class": "ECONOMY", "price": 89000},
        ),
        client.put(f"/seats/{SEAT_ID}", json={"price": 99000}),
        client.delete(f"/seats/{SEAT_ID}"),
    ]

    assert all(response.status_code == 403 for response in requests)


def test_admin_flight_list_returns_page(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "list_admin_flights",
        lambda *args, **kwargs: FlightPage(
            items=[], page=1, page_size=20, total=0, total_pages=0
        ),
    )

    response = create_client().get(
        "/admin/flights",
        params={"flight_number": "ke", "status": "SCHEDULED"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "total_pages": 0,
    }


def test_dashboard_route_returns_combined_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "get_admin_dashboard",
        lambda *args, **kwargs: AdminDashboardRead(
            flights=FlightMetrics(
                total=2, scheduled=1, delayed=1, cancelled=0, departed=0
            ),
            bookings=BookingMetrics(
                total=1, confirmed=1, cancelled=0, confirmed_revenue=89000
            ),
            chat_feedbacks=ChatFeedbackSummary(
                average_rating=4,
                rating_counts={1: 0, 2: 0, 3: 0, 4: 1, 5: 0},
                total_count=1,
                low_rating_count=0,
                low_rating_ratio=0,
            ),
            recent_events=[],
        ),
    )

    response = create_client().get("/admin/dashboard")

    assert response.status_code == 200
    assert response.json()["data"]["bookings"]["confirmed_revenue"] == 89000


def test_create_flight_conflict_maps_to_409(monkeypatch) -> None:
    def raise_conflict(*args, **kwargs):
        raise FlightConflictError

    monkeypatch.setattr(admin_router, "create_flight", raise_conflict)
    response = create_client().post("/flights", json=flight_create_body())

    assert response.status_code == 409
    assert response.json()["error_code"] == "FLIGHT_CONFLICT"


def test_delete_linked_flight_maps_to_409(monkeypatch) -> None:
    def raise_in_use(*args, **kwargs):
        raise FlightInUseError

    monkeypatch.setattr(admin_router, "delete_flight", raise_in_use)
    response = create_client().delete(f"/flights/{FLIGHT_ID}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "FLIGHT_IN_USE"


def test_delete_linked_seat_maps_to_409(monkeypatch) -> None:
    def raise_in_use(*args, **kwargs):
        raise SeatInUseError

    monkeypatch.setattr(admin_router, "delete_seat", raise_in_use)
    response = create_client().delete(f"/seats/{SEAT_ID}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "SEAT_IN_USE"


def test_successful_delete_returns_empty_204(monkeypatch) -> None:
    monkeypatch.setattr(admin_router, "delete_flight", lambda *args, **kwargs: None)
    response = create_client().delete(f"/flights/{FLIGHT_ID}")

    assert response.status_code == 204
    assert response.content == b""
