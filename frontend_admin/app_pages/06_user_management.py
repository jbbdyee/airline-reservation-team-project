"""관리자 사용자 목록과 권한 변경 화면."""

import streamlit as st

from clients.user_client import (
    get_admin_users,
    update_user_role,
)
from components.user_table import render_user_table
from core.api_client import BackendAPIError


st.title("사용자 관리")
st.caption("사용자 목록을 조회하고 역할을 변경합니다.")

try:
    users = get_admin_users(page=1)
except BackendAPIError as error:
    st.error(str(error))
    st.stop()

query = st.text_input("이름 또는 이메일 검색")

rows = [
    item
    for item in users
    if query.lower()
    in (
        f"{item.get('name', '')}"
        f"{item.get('email', '')}"
    ).lower()
]

render_user_table(rows)

if users:
    selected = st.selectbox(
        "사용자",
        users,
        format_func=lambda item: (
            f"{item.get('name')}"
            f" · {item.get('email')}"
        ),
    )

    role = st.selectbox(
        "역할",
        ["user", "admin"],
        index=["user", "admin"].index(
            selected.get("role", "user")
        ),
    )

    current_user = st.session_state.get(
        "user",
        {},
    )

    if st.button(
        "사용자 권한 저장",
        disabled=(
            selected.get("id")
            == current_user.get("id")
        ),
    ):
        try:
            update_user_role(
                selected["id"],
                role,
            )

            st.success(
                "사용자 권한을 변경했습니다."
            )
            st.rerun()

        except BackendAPIError as error:
            st.error(str(error))