import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.dn.supabase_client import get_supabase_client
from app.main import app

client = TestClient(app)


@pytest.fixture()
def signup_payload() -> dict:
    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"user_{unique}@example.com",
        "password": "TestPass1234!",
        "name": "사용자 테스트",
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


def test_get_and_update_my_profile(signup_payload, cleanup_user):
    token = signup_and_signin(signup_payload, cleanup_user)
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = client.get("/users/me", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == signup_payload["email"]

    update_response = client.patch(
        "/users/me",
        headers=headers,
        json={"name": "수정된 사용자", "phone": "010-1234-5678"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "수정된 사용자"
    assert update_response.json()["phone"] == "010-1234-5678"


def test_user_list_requires_admin(signup_payload, cleanup_user):
    token = signup_and_signin(signup_payload, cleanup_user)

    response = client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_admin_can_list_users(signup_payload, cleanup_user):
    token = signup_and_signin(signup_payload, cleanup_user)
    supabase = get_supabase_client()
    supabase.table("users").update({"role": "ADMIN"}).eq(
        "email", signup_payload["email"]
    ).execute()

    response = client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_admin_can_update_user_role(signup_payload, cleanup_user):
    admin_token = signup_and_signin(signup_payload, cleanup_user)
    supabase = get_supabase_client()
    supabase.table("users").update({"role": "ADMIN"}).eq(
        "email", signup_payload["email"]
    ).execute()

    target_payload = {
        "email": f"target_{uuid.uuid4().hex[:8]}@example.com",
        "password": "TestPass1234!",
        "name": "권한변경 대상",
    }
    target_response = client.post("/auth/signup", json=target_payload)
    assert target_response.status_code == 201
    cleanup_user.append(target_payload["email"])
    target_user_id = target_response.json()["id"]

    response = client.patch(
        f"/users/{target_user_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
