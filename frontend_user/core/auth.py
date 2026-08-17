import json

import streamlit as st
from streamlit_js import st_js_blocking


STORAGE_KEY = "airport_login_state"


def _load_login_from_browser() -> dict | None:
    """브라우저 sessionStorage에서 사용자 정보와 토큰을 읽습니다."""

    raw_value = st_js_blocking(
        code=f"""
            return sessionStorage.getItem({json.dumps(STORAGE_KEY)});
        """,
        key="load_airport_login_state",
    )

    if not raw_value:
        return None

    try:
        login_state = json.loads(raw_value)

        # 컴포넌트 반환값이 한 번 더 문자열로 감싸진 경우 처리
        if isinstance(login_state, str):
            login_state = json.loads(login_state)

        if not isinstance(login_state, dict):
            return None

        user = login_state.get("user")
        session_token = login_state.get("session_token")

        if not isinstance(user, dict) or not session_token:
            return None

        return {
            "user": user,
            "session_token": session_token,
        }

    except (TypeError, json.JSONDecodeError):
        return None


def _save_login_to_browser(user: dict) -> bool:
    """비밀번호를 제외한 사용자 정보와 세션 토큰을 저장합니다."""

    session_token = st.session_state.get("session_token")

    if not session_token:
        return False

    public_user = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "profile_image": user.get("profile_image", ""),
    }

    login_state = {
        "user": public_user,
        "session_token": session_token,
    }

    login_state_json = json.dumps(
        login_state,
        ensure_ascii=False,
    )

    result = st_js_blocking(
        code=f"""
            sessionStorage.setItem(
                {json.dumps(STORAGE_KEY)},
                {json.dumps(login_state_json)}
            );
            return true;
        """,
        key="save_airport_login_state",
    )

    return result is True


def _remove_login_from_browser() -> bool:
    """브라우저 sessionStorage의 로그인 정보를 삭제합니다."""

    result = st_js_blocking(
        code=f"""
            sessionStorage.removeItem({json.dumps(STORAGE_KEY)});
            sessionStorage.removeItem("airport_logged_in_user");
            return true;
        """,
        key="remove_airport_login_state",
    )

    return result is True


def begin_login(user: dict) -> None:
    """로그인 후 브라우저에 로그인 정보 저장을 예약합니다."""

    st.session_state["user"] = user
    st.session_state["_pending_browser_login"] = user
    st.rerun()


def restore_login() -> None:
    """새로고침 후 브라우저 sessionStorage에서 로그인 정보를 복원합니다."""

    if (
        st.session_state.get("user")
        and st.session_state.get("session_token")
    ):
        return

    login_state = _load_login_from_browser()

    if not login_state:
        return

    st.session_state["user"] = login_state["user"]
    st.session_state["session_token"] = login_state["session_token"]


def sync_login_state() -> None:
    """앱 시작 시 로그인 저장·복원·로그아웃을 처리합니다."""

    pending_user = st.session_state.get("_pending_browser_login")

    if pending_user:
        if _save_login_to_browser(pending_user):
            st.session_state.pop("_pending_browser_login", None)
            st.switch_page("app_pages/02_search.py")
        return

    if st.session_state.get("_pending_browser_logout"):
        if _remove_login_from_browser():
            st.session_state.pop("_pending_browser_logout", None)
        return

    restore_login()


def require_login() -> None:
    """사용자 정보와 인증 토큰이 모두 있을 때만 접근을 허용합니다."""

    if (
        not st.session_state.get("user")
        or not st.session_state.get("session_token")
    ):
        st.warning("이 기능은 로그인 후 이용할 수 있습니다.")
        st.page_link(
            "app_pages/01_login.py",
            label="로그인 페이지로 이동",
            icon="🔐",
        )
        st.stop()


def logout() -> None:
    """세션과 브라우저에 저장한 로그인 정보를 삭제합니다."""

    for key in [
        "user",
        "session_token",
        "selected_flight",
        "selected_seats",
        "chat_messages",
        "chat_ended",
    ]:
        st.session_state.pop(key, None)

    st.session_state["_pending_browser_logout"] = True