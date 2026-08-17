import streamlit as st

from clients.auth_client import signin, signup
from core.api_client import BackendAPIError
from core.auth import begin_login

st.title("로그인 / 회원가입")

login_tab, signup_tab = st.tabs(
    ["로그인", "회원가입"]
)

with login_tab:
    st.subheader("로그인")

    with st.form("login_form"):
        email = st.text_input(
            "이메일",
            key="login_email",
            placeholder="user@example.com",
        )

        password = st.text_input(
            "비밀번호",
            type="password",
            key="login_password",
        )

        submitted = st.form_submit_button(
            "로그인",
            type="primary",
        )

    if submitted:
        try:
            user = signin(email, password)
            begin_login(user)

        except BackendAPIError as error:
            st.error(str(error))


with signup_tab:
    st.subheader("회원가입")

    with st.form("signup_form"):
        name = st.text_input(
            "이름",
            key="signup_name",
        )

        email = st.text_input(
            "이메일",
            key="signup_email",
            placeholder="user@example.com",
        )

        password = st.text_input(
            "비밀번호",
            type="password",
            key="signup_password",
            help="비밀번호는 8자 이상 입력해 주세요.",
        )

        submitted = st.form_submit_button(
            "회원가입",
            type="primary",
        )

    if submitted:
        try:
            user = signup(email, password, name)
            begin_login(user)

        except BackendAPIError as error:
            st.error(str(error))