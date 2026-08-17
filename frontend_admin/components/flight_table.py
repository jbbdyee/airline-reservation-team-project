"""항공편 목록 테이블 컴포넌트."""

import pandas as pd
import streamlit as st


def render_flight_table(flights: list[dict]) -> None:
    if flights:
        st.dataframe(pd.DataFrame(flights), use_container_width=True, hide_index=True)
    else:
        st.info("조회된 항공편이 없습니다.")
