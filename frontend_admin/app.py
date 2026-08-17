"""항공권 예약 서비스 관리자 Streamlit 애플리케이션."""

import streamlit as st
from streamlit_session_browser_storage import SessionStorage

from clients.auth_client import signout
from core.api_client import BackendAPIError
from core.auth import (
    init_state,
    is_admin,
    is_logged_in,
    logout,
    restore_login,
)

st.set_page_config(
    page_title="항공권 예약 관리자",
    page_icon="✈️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 85% 5%, #dff4ff 0%, transparent 25%),
                    linear-gradient(180deg, #f7fcff 0%, #eef8ff 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fff 0%, #e9f7ff 100%);
        border-right: 1px solid #cbeafe;
    }
    [data-testid="stSidebar"] * { color: #0f3b57; }
    h1, h2, h3 { color: #075985; }
    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid #bae6fd;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 6px 18px rgba(14, 165, 233, .08);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, .94);
        border: 1px solid #bae6fd !important;
        border-radius: 18px;
        box-shadow: 0 8px 22px rgba(14, 165, 233, .08);
    }
    .stButton > button, .stFormSubmitButton > button {
        border: 0;
        border-radius: 10px;
        background: linear-gradient(135deg, #0ea5e9, #0284c7);
        color: #fff;
        font-weight: 700;
    }
    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, .82);
        border: 1px solid #d7effc;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_state()

storage = SessionStorage(key="admin_login_storage")


def clear_saved_login() -> None:
    """Streamlit 상태와 브라우저 탭의 로그인 정보를 삭제합니다."""

    storage.deleteAll(key="clear_admin_login_storage")
    logout()


def restore_saved_login() -> None:
    """새로고침 시 브라우저에 저장된 토큰으로 로그인 상태를 복원합니다."""

    # 로그인 직후에는 토큰을 브라우저 저장소에 저장
    if is_logged_in():
        token = st.session_state.get(
            "access_token",
            "",
        )

        if token:
            storage.setItem(
                "session_token",
                token,
                key="save_admin_session_token",
            )

        return

    # 새로고침으로 Streamlit 세션이 초기화된 경우
    saved_token = storage.getItem(
        "session_token"
    )

    if not saved_token:
        return

    # 인자는 token 하나만 전달
    if not restore_login(saved_token):
        storage.deleteAll(
            key="delete_invalid_admin_login"
        )

restore_saved_login()
authenticated = is_admin()

login_page = st.Page("app_pages/01_login.py", title="관리자 로그인", icon="🔐",default=True,)
dashboard_page = st.Page("app_pages/02_dashboard.py", title="운영 대시보드", icon="📊",url_path="dashboard",)
flight_page = st.Page("app_pages/03_flight_management.py", title="항공편 관리", icon="✈️",url_path="flights",)
seat_page = st.Page("app_pages/04_seat_management.py", title="좌석 관리", icon="💺",url_path="seats",)
booking_page = st.Page("app_pages/05_booking_management.py", title="예약 관리", icon="🎫",url_path="bookings",)
user_page = st.Page("app_pages/06_user_management.py", title="사용자 관리", icon="👥",url_path="users",)
realtime_page = st.Page("app_pages/07_realtime_monitor.py", title="실시간 모니터", icon="📡",url_path="realtime",)
feedback_page = st.Page("app_pages/08_feedback_management.py", title="피드백 관리", icon="💬",url_path="feedback",)

admin_pages = [
    dashboard_page,
    flight_page,
    seat_page,
    booking_page,
    user_page,
    realtime_page,
    feedback_page,
]

all_pages = [
    login_page,
    *admin_pages,
]

navigation = st.navigation(
    all_pages,
    position="hidden",

)

with st.sidebar:
    st.title("✈️ 항공권 관리자")
    st.caption("관리자 프론트엔드 · tk")
    st.divider()
    if authenticated:
        for page in admin_pages:
            st.page_link(page)
        st.divider()
        admin_name = st.session_state.get(
            "user",
            {},
        ).get(
            "name",
            "관리자",
        )

        st.write(f"관리자: {admin_name}")
        if st.button("로그아웃", use_container_width=True):
            try:
                signout()
            except BackendAPIError as error:
                st.warning(f"서버 로그아웃 처리 실패: {error}")
            finally:
                clear_saved_login()
                st.rerun()
    else:
        st.page_link(login_page)
if authenticated:
    current_path = navigation.url_path
    admin_page_by_path = {
    "dashboard": dashboard_page,
    "flights": flight_page,
    "seats": seat_page,
    "bookings": booking_page,
    "users": user_page,
    "realtime": realtime_page,
    "feedback": feedback_page,
    }

    if current_path in admin_page_by_path:
        # 현재 보고 있는 페이지를 브라우저에 저장
        storage.setItem(
            "last_admin_page",
            current_path,
            key="save_last_admin_page",
        )

        navigation.run()

    else:
        # 새로고침 과정에서 현재 URL을 잃어버렸다면
        # 브라우저에 저장된 마지막 페이지를 복원
        last_page_path = storage.getItem(
            "last_admin_page"
        )

        target_page = admin_page_by_path.get(
            last_page_path,
            dashboard_page,
        )

        st.switch_page(target_page)

else:
    if navigation.url_path == login_page.url_path:
        navigation.run()
    else:
        st.info("로그인 정보를 복원하고 있습니다.")

        st.page_link(
            login_page,
            label="관리자 로그인으로 이동",
            icon="🔐",
        )