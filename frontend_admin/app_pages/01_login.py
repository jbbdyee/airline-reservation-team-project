"""관리자 로그인 화면."""

import streamlit as st
import httpx
from clients.auth_client import signin
from core.api_client import BackendAPIError
from core.auth import login


st.title("✈️ 관리자 로그인")
st.caption("항공권 예약 서비스의 관리자 전용 화면입니다.")

left, center, right = st.columns([1, 1.2, 1])
with center:
    with st.container(border=True):
        with st.form("admin_login_form"):
            email = st.text_input("관리자 이메일", value="admin@skyops.dev")
            password = st.text_input("비밀번호", type="password", value="admin1234")
            submitted = st.form_submit_button("로그인", use_container_width=True)

        if submitted:
            if not email.strip() or not password:
                st.warning("이메일과 비밀번호를 모두 입력해 주세요.")
            else:
                try:
                    result = signin(email.strip(), password)
                    user = result.get("user", result.get("account", {}))
                    if user.get("role") != "ADMIN":
                        st.error("관리자 권한이 없는 계정입니다.")
                    else:
                        login(result)
                        st.switch_page(
                        "app_pages/02_dashboard.py"
                        )
                except BackendAPIError as error:
                    st.error(str(error))

        st.info("데모 계정: admin@skyops.dev / admin1234")
