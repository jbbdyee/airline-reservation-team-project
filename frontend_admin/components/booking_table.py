"""예약 목록 테이블 컴포넌트."""

import pandas as pd
import streamlit as st


def render_booking_table(
    bookings: list[dict],
) -> None:
    if bookings:
        st.dataframe(
            pd.DataFrame(bookings),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("조회된 예약이 없습니다.")