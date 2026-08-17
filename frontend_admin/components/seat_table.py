"""좌석 목록 테이블 컴포넌트."""

import pandas as pd
import streamlit as st


def render_seat_table(seats: list[dict]) -> None:
    if seats:
        st.dataframe(pd.DataFrame(seats), use_container_width=True, hide_index=True)
    else:
        st.info("등록된 좌석이 없습니다.")
