"""기존 사용자 관리 화면과 백엔드 API를 연결하는 클라이언트."""

from __future__ import annotations

from typing import Any

from core.api_client import as_list, request


ROLE_TO_API = {
    "user": "USER",
    "admin": "ADMIN",
}

ROLE_TO_FRONTEND = {
    "USER": "user",
    "ADMIN": "admin",
}


def _normalize_user(
    user: dict[str, Any],
) -> dict[str, Any]:
    backend_role = str(
        user.get("role", "USER")
    ).upper()

    return {
        "id": user.get("id", ""),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone") or "",
        "role": ROLE_TO_FRONTEND.get(
            backend_role,
            backend_role.lower(),
        ),
        "profile_image_url": user.get(
            "profile_image_url"
        ) or "",
        "created_at": user.get("created_at", ""),
    }


def get_admin_users(
    role: str | None = None,
    page: int = 1,
) -> list[dict]:
    """
    기존 페이지가 기대하는 list 형식으로 사용자를 반환합니다.
    """

    page_size = 100
    offset = (page - 1) * page_size

    payload = request(
        "GET",
        "/users",
        params={
            "offset": offset,
            "limit": page_size,
        },
    )

    users = [
        _normalize_user(user)
        for user in as_list(payload)
        if isinstance(user, dict)
    ]

    if role:
        frontend_role = role.lower()

        users = [
            user
            for user in users
            if user.get("role") == frontend_role
        ]

    return users


def update_user_role(
    user_id: str,
    role: str,
) -> dict:
    backend_role = ROLE_TO_API.get(
        role.lower(),
        role.upper(),
    )

    payload = request(
        "PATCH",
        f"/users/{user_id}/role",
        json={
            "role": backend_role,
        },
    )

    if not isinstance(payload, dict):
        return {}

    return _normalize_user(payload)