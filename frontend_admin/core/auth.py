"""관리자 로그인 상태와 인증 동작을 관리합니다."""

import streamlit as st

from core.api_client import BackendAPIError, request


def init_state() -> None:
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("access_token", "")
    st.session_state.setdefault("user", {})


def _normalize_user(user: dict) -> dict:
    normalized_user = dict(user)

    normalized_user["role"] = str(
        normalized_user.get("role", "")
    ).strip().lower()

    return normalized_user


def _clear_state() -> None:
    st.session_state.logged_in = False
    st.session_state.access_token = ""
    st.session_state.user = {}


def login(login_result: dict) -> None:
    """백엔드 로그인 응답을 Streamlit 세션에 저장합니다."""

    session_token = login_result.get("session_token")
    user = login_result.get("user")

    if not session_token or not isinstance(user, dict):
        raise BackendAPIError(
            "로그인 응답에 session_token 또는 사용자 정보가 없습니다."
        )

    normalized_user = _normalize_user(user)

    # role은 소문자 admin으로 통일
    if normalized_user.get("role") != "admin":
        raise BackendAPIError("관리자 계정만 로그인할 수 있습니다.")

    st.session_state.logged_in = True
    st.session_state.access_token = session_token
    st.session_state.user = normalized_user


def restore_login(token: str) -> bool:
    """저장된 토큰을 백엔드에서 검증하고 로그인 상태를 복원합니다."""

    if not token:
        _clear_state()
        return False

    # api_client.request()가 이 값을 읽어서
    # Authorization: Bearer {token} 헤더를 생성함
    st.session_state.access_token = token

    try:
        result = request(
            "GET",
            "/users/me",
        )
    except BackendAPIError:
        _clear_state()
        return False

    user = result.get("user", result)

    if not isinstance(user, dict):
        _clear_state()
        return False

    normalized_user = _normalize_user(user)

    if normalized_user.get("role") != "admin":
        _clear_state()
        return False

    st.session_state.logged_in = True
    st.session_state.access_token = token
    st.session_state.user = normalized_user

    return True


def logout() -> None:
    _clear_state()


def is_logged_in() -> bool:
    return bool(
        st.session_state.get("logged_in")
        and st.session_state.get("access_token")
    )


def is_admin() -> bool:
    role = str(
        st.session_state.get("user", {}).get("role", "")
    ).strip().lower()

    # 기존 코드의 role.lower() == "ADMIN"이 문제였음
    return is_logged_in() and role == "admin"