"""피드백 목록 테이블 컴포넌트."""

import pandas as pd
import streamlit as st


def render_feedback_table(feedbacks: list[dict]) -> None:
    if feedbacks:
        st.dataframe(pd.DataFrame(feedbacks), use_container_width=True, hide_index=True)
    else:
        st.info("조회된 피드백이 없습니다.")
