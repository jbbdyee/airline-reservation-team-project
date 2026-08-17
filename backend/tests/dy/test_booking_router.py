from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.core.dy.principal import InvalidPrincipalError, principal_user_id
from app.routers.dy import booking_router
from app.services.dy.booking_service import BookingNotFoundError, SeatAlreadyBookedError


USER_ID = "00000000-0000-0000-0000-00000000b002"
BOOKING_ID = "00000000-0000-0000-0000-00000000e001"


def current_user():
    return {"user_id": USER_ID, "role": "USER"}


def denied_admin():
    raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def create_client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(
        booking_router.build_booking_router(current_user, denied_admin)
    )
    app.dependency_overrides[get_supabase] = lambda: object()
    return TestClient(app)


def test_principal_adapter_accepts_id_or_user_id() -> None:
    assert principal_user_id({"id": USER_ID}) == UUID(USER_ID)
    assert principal_user_id({"user_id": USER_ID}) == UUID(USER_ID)

    class Principal:
        id = USER_ID

    assert principal_user_id(Principal()) == UUID(USER_ID)


def test_principal_adapter_rejects_missing_or_invalid_id() -> None:
    try:
        principal_user_id({})
    except InvalidPrincipalError:
        pass
    else:
        raise AssertionError("ID 없는 principal이 허용되었습니다.")


def test_booking_route_maps_service_not_found(monkeypatch) -> None:
    def raise_not_found(*args, **kwargs):
        raise BookingNotFoundError

    monkeypatch.setattr(booking_router, "get_booking", raise_not_found)
    client = create_client(monkeypatch)

    response = client.get(f"/bookings/{BOOKING_ID}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "BOOKING_NOT_FOUND"


def test_booking_create_maps_seat_conflict(monkeypatch) -> None:
    def raise_conflict(*args, **kwargs):
        raise SeatAlreadyBookedError

    monkeypatch.setattr(booking_router, "create_booking", raise_conflict)
    client = create_client(monkeypatch)

    response = client.post(
        "/bookings",
        json={
            "flight_id": "00000000-0000-0000-0000-00000000c001",
            "seat_id": "00000000-0000-0000-0000-00000000d001",
            "passenger_name": "테스트유저",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "SEAT_ALREADY_BOOKED"


def test_admin_booking_route_uses_separate_admin_dependency(monkeypatch) -> None:
    client = create_client(monkeypatch)

    response = client.get("/admin/bookings")

    assert response.status_code == 403
    assert response.json()["detail"] == "관리자 권한이 필요합니다."


def test_booking_query_validation_happens_before_service(monkeypatch) -> None:
    client = create_client(monkeypatch)

    response = client.get("/bookings/me", params={"page": 0})

    assert response.status_code == 422
