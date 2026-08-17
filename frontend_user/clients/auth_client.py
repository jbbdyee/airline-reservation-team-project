import os
import re
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

from core.api_client import BackendAPIError


FRONTEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(FRONTEND_DIR / ".env")

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "https://airline-reservation-team-project.onrender.com",
).rstrip("/")
# BACKEND_URL = os.getenv(
#     "BACKEND_URL",
#     "http://localhost:8000",
# ).rstrip("/")

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def _validate_email(email: str) -> str:
    email = email.strip().lower()

    if not email:
        raise BackendAPIError(
            "이메일을 입력해 주세요."
        )

    if not EMAIL_PATTERN.fullmatch(email):
        raise BackendAPIError(
            "올바른 이메일 형식으로 입력해 주세요."
        )

    return email


def _validate_password(password: str) -> None:
    if not password:
        raise BackendAPIError(
            "비밀번호를 입력해 주세요."
        )

    # 백엔드 SignupRequest 조건과 동일하게 설정
    if len(password) < 8:
        raise BackendAPIError(
            "비밀번호는 8자 이상 입력해 주세요."
        )




def _validate_name(name: str) -> str:
    name = name.strip()

    if not name:
        raise BackendAPIError(
            "이름을 입력해 주세요."
        )



    return name


def _request(
    method: str,
    path: str,
    **kwargs: Any,
) -> dict:
    """백엔드 API를 호출하고 오류 응답을 공통 처리합니다."""

    try:
        response = httpx.request(
            method=method,
            url=f"{BACKEND_URL}{path}",
            timeout=60,
            **kwargs,
        )

    except httpx.ConnectError as error:
        raise BackendAPIError(
            "백엔드 서버에 연결할 수 없습니다. "
            "서버가 실행 중인지 확인해 주세요."
        ) from error

    except httpx.TimeoutException as error:
        raise BackendAPIError(
            "백엔드 서버의 응답 시간이 초과되었습니다."
        ) from error

    except httpx.HTTPError as error:
        raise BackendAPIError(
            "백엔드 통신 중 오류가 발생했습니다."
        ) from error

    # 로그아웃 성공 응답은 204이며 본문이 없습니다.
    if response.status_code == 204:
        return {}

    try:
        body = response.json()
    except ValueError as error:
        raise BackendAPIError(
            "백엔드에서 올바르지 않은 응답을 반환했습니다."
        ) from error

    if not response.is_success:
        message = body.get(
            "message",
            "요청 처리 중 오류가 발생했습니다.",
        )

        raise BackendAPIError(message)

    return body


def _normalize_user(user: dict) -> dict:
    """기존 프론트 코드와 백엔드 필드 이름을 호환합니다."""

    normalized = dict(user)

    # 백엔드: id
    # 기존 프론트: user_id
    normalized["user_id"] = normalized["id"]

    # 백엔드: profile_image_url
    # 기존 프론트: profile_image
    normalized["profile_image"] = (
        normalized.get("profile_image_url") or ""
    )

    return normalized


def signup(
    email: str,
    password: str,
    name: str,
) -> dict:
    """회원가입 후 바로 로그인합니다."""

    email = _validate_email(email)
    _validate_password(password)
    name = _validate_name(name)

    _request(
        "POST",
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "name": name,
        },
    )

    # 회원가입 API는 세션을 만들지 않기 때문에
    # 회원가입 성공 후 로그인 API를 추가 호출합니다.
    return signin(
        email=email,
        password=password,
    )


def signin(
    email: str,
    password: str,
) -> dict:
    """로그인하고 세션 토큰과 사용자 정보를 저장합니다."""

    email = _validate_email(email)

    if not password:
        raise BackendAPIError(
            "비밀번호를 입력해 주세요."
        )

    # /auth/signin은 JSON이 아니라 Form 데이터를 받습니다.
    body = _request(
        "POST",
        "/auth/signin",
        data={
            "email": email,
            "password": password,
        },
    )

    session_token = body.get("session_token")
    user = body.get("user")

    if not session_token or not user:
        raise BackendAPIError(
            "로그인 응답에 사용자 또는 세션 정보가 없습니다."
        )

    st.session_state["session_token"] = session_token

    return _normalize_user(user)


def get_my_profile() -> dict:
    """현재 로그인한 사용자의 최신 정보를 조회합니다."""

    token = st.session_state.get("session_token")

    if not token:
        raise BackendAPIError(
            "로그인이 필요합니다."
        )

    user = _request(
        "GET",
        "/users/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    return _normalize_user(user)


def update_profile(
    user_id: str,
    name: str,
    profile_image: Any,
) -> dict:
    """이미지를 업로드한 후 프로필 URL을 저장합니다."""

    del user_id

    token = st.session_state.get("session_token")

    if not token:
        raise BackendAPIError(
            "로그인이 필요합니다."
        )

    name = _validate_name(name)

    profile_image_url: str | None

    # 새 Streamlit 업로드 파일이 전달된 경우
    if hasattr(profile_image, "getvalue"):
        upload_body = _request(
            "POST",
            "/uploads/images",
            headers={
                "Authorization": f"Bearer {token}",
            },
            files={
                "file": (
                    profile_image.name,
                    profile_image.getvalue(),
                    profile_image.type,
                )
            },
        )

        upload_data = upload_body.get("data", {})

        profile_image_url = upload_data.get("url")

        if not profile_image_url:
            raise BackendAPIError(
                "이미지 업로드 응답에 URL이 없습니다."
            )

    # 기존 이미지 URL이 전달된 경우
    elif isinstance(profile_image, str):
        profile_image_url = (
            profile_image.strip() or None
        )

    else:
        profile_image_url = None

    user = _request(
        "PATCH",
        "/users/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "name": name,
            "profile_image_url": profile_image_url,
        },
    )

    return _normalize_user(user)

def signout() -> None:
    """백엔드 세션을 삭제하고 프론트 로그인 정보를 정리합니다."""

    token = st.session_state.get("session_token")

    if token:
        _request(
            "POST",
            "/auth/signout",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

    for key in [
        "session_token",
        "user",
        "selected_flight",
        "selected_seats",
        "chat_messages",
    ]:
        st.session_state.pop(key, None)
