import streamlit as st

from core.auth import logout, sync_login_state


st.set_page_config(
    page_title="Airport",
    layout="wide",
)


# 페이지 URL과 기본 페이지는 로그인 상태와 관계없이 항상 동일하게 유지합니다.
login_page = st.Page(
    "app_pages/01_login.py",
    title="로그인",
    icon="🔐",
    url_path="login",
)

search_page = st.Page(
    "app_pages/02_search.py",
    title="항공편 검색",
    icon="✈️",
    default=True,
)

flight_detail_page = st.Page(
    "app_pages/03_flight_detail.py",
    title="항공편 상세",
    icon="🛫",
    url_path="flight-detail",
)

booking_page = st.Page(
    "app_pages/04_booking.py",
    title="예약 확인",
    icon="🎫",
    url_path="booking",
)

my_bookings_page = st.Page(
    "app_pages/05_my_bookings.py",
    title="내 예약",
    icon="📋",
    url_path="my-bookings",
)

chat_page = st.Page(
    "app_pages/06_chat.py",
    title="AI 여행 도우미",
    icon="🤖",
    url_path="chat",
)

profile_page = st.Page(
    "app_pages/07_profile.py",
    title="프로필",
    icon="👤",
    url_path="profile",
)

feedback_page = st.Page(
    "app_pages/08_feedback.py",
    title="챗봇 평가",
    icon="⭐",
    url_path="feedback",
)


public_pages = [
    search_page,
    flight_detail_page,
    chat_page,
]

private_pages = [
    booking_page,
    my_bookings_page,
    profile_page,
    feedback_page,
]

all_pages = [
    login_page,
    *public_pages,
    *private_pages,
]


# 새 세션의 첫 실행에서도 현재 URL을 찾을 수 있도록 인증 복원보다 먼저
# 모든 페이지를 등록합니다. 내장 메뉴는 숨기고 아래에서 직접 구성합니다.
navigation = st.navigation(
    all_pages,
    position="hidden",
)


# sessionStorage에 저장된 로그인 정보를 복원합니다.
sync_login_state()

user = st.session_state.get("user")
is_logged_in = bool(user)


with st.sidebar:
    st.title("Airport")

    if not is_logged_in:
        st.page_link(login_page)

    for page in public_pages:
        st.page_link(page)

    if is_logged_in:
        for page in private_pages:
            st.page_link(page)

        st.divider()
        st.write(f"로그인 사용자: {user['name']}")

        if st.button(
            "로그아웃",
            use_container_width=True,
        ):
            logout()
            st.rerun()


# 로그인된 사용자가 로그인 URL을 직접 열면 검색 화면으로 이동합니다.
if is_logged_in and navigation.url_path == login_page.url_path:
    st.switch_page(search_page)

navigation.run()
