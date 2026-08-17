
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase_client
from app.main import app
from app.services.dn import chat_service

client = TestClient(app)


@pytest.fixture()
def signup_payload() -> dict:
    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"test_{unique}@example.com",
        "password": "TestPass1234!",
        "name": "테스트유저",
    }


@pytest.fixture()
def cleanup_user():
    created_emails: list[str] = []
    yield created_emails
    supabase = get_supabase_client()
    for email in created_emails:
        result = supabase.table("users").select("id").eq("email", email).execute()
        user = result.data[0] if result.data else None
        if user is not None:
            # users 삭제 전에 외래 키로 연결된 테스트 데이터부터 정리한다.
            supabase.table("chat_messages").delete().eq("user_id", user["id"]).execute()
            supabase.table("sessions").delete().eq("user_id", user["id"]).execute()
        supabase.table("users").delete().eq("email", email).execute()


def signup_and_signin(signup_payload: dict, cleanup_user: list[str]) -> str:
    signup_response = client.post("/auth/signup", json=signup_payload)
    assert signup_response.status_code == 201
    cleanup_user.append(signup_payload["email"])

    signin_response = client.post(
        "/auth/signin",
        data={"email": signup_payload["email"], "password": signup_payload["password"]},
    )
    assert signin_response.status_code == 200
    return signin_response.json()["session_token"]


def test_signup_success(signup_payload, cleanup_user):
    response = client.post("/auth/signup", json=signup_payload)
    cleanup_user.append(signup_payload["email"])

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == signup_payload["email"]
    assert "password_hash" not in body


def test_signup_duplicate_email_fails(signup_payload, cleanup_user):
    client.post("/auth/signup", json=signup_payload)
    cleanup_user.append(signup_payload["email"])

    response = client.post("/auth/signup", json=signup_payload)

    assert response.status_code == 409
    assert response.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def test_signin_success(signup_payload, cleanup_user):
    client.post("/auth/signup", json=signup_payload)
    cleanup_user.append(signup_payload["email"])

    response = client.post(
        "/auth/signin",
        data={"email": signup_payload["email"], "password": signup_payload["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_token"]
    assert body["user"]["email"] == signup_payload["email"]


def test_signin_wrong_password_fails(signup_payload, cleanup_user):
    client.post("/auth/signup", json=signup_payload)
    cleanup_user.append(signup_payload["email"])

    response = client.post(
        "/auth/signin",
        data={"email": signup_payload["email"], "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_signout_success(signup_payload, cleanup_user):
    client.post("/auth/signup", json=signup_payload)
    cleanup_user.append(signup_payload["email"])

    signin_response = client.post(
        "/auth/signin",
        data={"email": signup_payload["email"], "password": signup_payload["password"]},
    )
    token = signin_response.json()["session_token"]

    response = client.post("/auth/signout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204


def test_chat_message_saves_user_and_assistant_messages(
    signup_payload,
    cleanup_user,
    monkeypatch,
):
    monkeypatch.setattr(
        chat_service,
        "_request_gemini_answer",
        lambda message: "테스트용 Gemini 응답입니다.",
    )
    token = signup_and_signin(signup_payload, cleanup_user)

    response = client.post(
        "/chat/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "항공권 검색 방법을 알려주세요."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "테스트용 Gemini 응답입니다."
    assert body["conversation_id"]
    assert body["user_message_id"]
    assert body["assistant_message_id"]
