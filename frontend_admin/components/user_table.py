"""사용자 목록 테이블 컴포넌트."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_user_table(users: list[dict]) -> None:
    """관리자 화면에 사용자 목록을 표시합니다."""

    if not users:
        st.info("조회된 사용자가 없습니다.")
        return

    table_rows = [
        {
            "이름": user.get("name", ""),
            "이메일": user.get("email", ""),
            "전화번호": user.get("phone", "-"),
            "권한": user.get("role_label", user.get("role", "")),
            "가입 일시": user.get("created_at", "-"),
        }
        for user in users
    ]

    dataframe = pd.DataFrame(table_rows)

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "이름": st.column_config.TextColumn(
                "이름",
                width="medium",
            ),
            "이메일": st.column_config.TextColumn(
                "이메일",
                width="large",
            ),
            "전화번호": st.column_config.TextColumn(
                "전화번호",
                width="medium",
            ),
            "권한": st.column_config.TextColumn(
                "권한",
                width="small",
            ),
            "가입 일시": st.column_config.TextColumn(
                "가입 일시",
                width="medium",
            ),
        },
    )