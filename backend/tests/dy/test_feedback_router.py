from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase
from app.routers.dy import feedback_router
from app.schemas.dy.feedback_schema import ChatFeedbackSummary
from app.services.dy.feedback_service import (
    AssistantMessageMismatchError,
    ChatFeedbackAlreadyExistsError,
    FeedbackNotFoundError,
)


USER_ID = "00000000-0000-0000-0000-00000000b002"
FEEDBACK_ID = "00000000-0000-0000-0000-200000000001"
CONVERSATION_ID = "00000000-0000-0000-0000-0000000000f1"
ASSISTANT_MESSAGE_ID = "00000000-0000-0000-0000-100000000002"


def current_user():
    return {"id": USER_ID, "role": "USER"}


def denied_admin():
    raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def create_client() -> TestClient:
    app = FastAPI()
    app.include_router(
        feedback_router.build_feedback_router(current_user, denied_admin)
    )
    app.dependency_overrides[get_supabase] = lambda: object()
    return TestClient(app)


def chat_feedback_body() -> dict:
    return {
        "conversation_id": CONVERSATION_ID,
        "assistant_message_id": ASSISTANT_MESSAGE_ID,
        "rating": 2,
        "comment": "설명이 부족해요",
    }


def test_chat_feedback_duplicate_maps_to_409(monkeypatch) -> None:
    def raise_duplicate(*args, **kwargs):
        raise ChatFeedbackAlreadyExistsError

    monkeypatch.setattr(feedback_router, "create_chat_feedback", raise_duplicate)
    response = create_client().post("/chat/feedbacks", json=chat_feedback_body())

    assert response.status_code == 409
    assert response.json()["error_code"] == "CHAT_FEEDBACK_ALREADY_EXISTS"


def test_chat_feedback_message_mismatch_maps_to_422(monkeypatch) -> None:
    def raise_mismatch(*args, **kwargs):
        raise AssistantMessageMismatchError

    monkeypatch.setattr(feedback_router, "create_chat_feedback", raise_mismatch)
    response = create_client().post("/chat/feedbacks", json=chat_feedback_body())

    assert response.status_code == 422
    assert response.json()["error_code"] == "ASSISTANT_MESSAGE_MISMATCH"


def test_admin_feedback_routes_require_admin_dependency() -> None:
    response = create_client().get("/admin/feedbacks")

    assert response.status_code == 403


def test_admin_chat_summary_route_serializes_metrics(monkeypatch) -> None:
    def allowed_admin():
        return {"id": USER_ID, "role": "ADMIN"}

    monkeypatch.setattr(
        feedback_router,
        "summarize_chat_feedbacks",
        lambda *args, **kwargs: ChatFeedbackSummary(
            average_rating=2.5,
            rating_counts={1: 1, 2: 1, 3: 0, 4: 0, 5: 0},
            total_count=2,
            low_rating_count=2,
            low_rating_ratio=1,
        ),
    )
    app = FastAPI()
    app.include_router(
        feedback_router.build_feedback_router(current_user, allowed_admin)
    )
    app.dependency_overrides[get_supabase] = lambda: object()

    response = TestClient(app).get("/admin/chat-feedbacks/summary")

    assert response.status_code == 200
    assert response.json()["data"]["average_rating"] == 2.5


def test_admin_feedback_not_found_maps_to_common_404(monkeypatch) -> None:
    def allowed_admin():
        return {"id": USER_ID, "role": "ADMIN"}

    def raise_not_found(*args, **kwargs):
        raise FeedbackNotFoundError

    monkeypatch.setattr(feedback_router, "get_feedback", raise_not_found)
    app = FastAPI()
    app.include_router(
        feedback_router.build_feedback_router(current_user, allowed_admin)
    )
    app.dependency_overrides[get_supabase] = lambda: object()

    response = TestClient(app).get(f"/admin/feedbacks/{FEEDBACK_ID}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "FEEDBACK_NOT_FOUND"
