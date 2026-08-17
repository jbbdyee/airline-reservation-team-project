from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.routers.dy import event_router
from app.services.dy.event_service import EventLogNotFoundError


USER_ID = "00000000-0000-0000-0000-00000000b002"
FLIGHT_ID = "00000000-0000-0000-0000-00000000c001"


def current_user():
    return {"id": USER_ID, "role": "USER"}


def denied_admin():
    raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def create_client() -> TestClient:
    app = FastAPI()
    app.include_router(event_router.build_event_router(current_user, denied_admin))
    app.dependency_overrides[get_supabase] = lambda: object()
    return TestClient(app)


def test_admin_event_log_routes_require_admin() -> None:
    response = create_client().get("/admin/event-logs")

    assert response.status_code == 403


def test_event_log_detail_maps_missing_log_to_404(monkeypatch) -> None:
    def allowed_admin():
        return {"id": USER_ID, "role": "ADMIN"}

    def raise_not_found(*args, **kwargs):
        raise EventLogNotFoundError

    monkeypatch.setattr(event_router, "get_event_log", raise_not_found)
    app = FastAPI()
    app.include_router(event_router.build_event_router(current_user, allowed_admin))
    app.dependency_overrides[get_supabase] = lambda: object()

    response = TestClient(app).get("/admin/event-logs/999")

    assert response.status_code == 404
    assert response.json()["error_code"] == "EVENT_LOG_NOT_FOUND"


def test_sse_new_connection_starts_after_latest_event(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(event_router, "get_latest_event_id", lambda client: 12)

    async def finite_stream(client, last_event_id, flight_id=None, **kwargs):
        captured["last_event_id"] = last_event_id
        captured["flight_id"] = flight_id
        yield 'id: 13\nevent: booking_changed\ndata: {"id": 13}\n\n'

    monkeypatch.setattr(event_router, "stream_event_logs", finite_stream)

    response = create_client().get(
        "/events/stream",
        params={"flight_id": FLIGHT_ID},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert captured["last_event_id"] == 12
    assert str(captured["flight_id"]) == FLIGHT_ID
    assert response.text.startswith("id: 13\n")


def test_sse_reconnect_header_and_query_cursor_precedence(monkeypatch) -> None:
    cursors: list[int] = []

    async def finite_stream(client, last_event_id, **kwargs):
        cursors.append(last_event_id)
        yield "event: heartbeat\ndata: {}\n\n"

    monkeypatch.setattr(event_router, "stream_event_logs", finite_stream)
    client = create_client()

    header_response = client.get(
        "/events/stream",
        headers={"Last-Event-ID": "7"},
    )
    query_response = client.get(
        "/events/stream",
        params={"last_event_id": 9},
        headers={"Last-Event-ID": "7"},
    )

    assert header_response.status_code == 200
    assert query_response.status_code == 200
    assert cursors == [7, 9]


def test_sse_requires_authenticated_user() -> None:
    def denied_user():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    app = FastAPI()
    app.include_router(event_router.build_event_router(denied_user, denied_admin))
    app.dependency_overrides[get_supabase] = lambda: object()

    response = TestClient(app).get("/events/stream")

    assert response.status_code == 401
