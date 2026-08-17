"""관리자 예약 목록과 상태 변경 화면."""

import streamlit as st
import pandas as pd

from clients.booking_client import (
    get_admin_bookings,
    update_booking_status,
)
from components.booking_table import render_booking_table
from core.api_client import BackendAPIError


st.title("예약 관리")
st.caption("전체 예약을 조회하고 예약 처리 상태를 변경합니다.")

column1, column2 = st.columns(2)

query = column1.text_input(
    "예약 ID 또는 탑승객 검색"
)

status_filter = column2.selectbox(
    "예약 상태",
    ["전체", "확정", "취소"],
)

try:
    bookings = get_admin_bookings(
        None if status_filter == "전체" else status_filter,
        page=1,
    )
except BackendAPIError as error:
    st.error(str(error))
    st.stop()

rows = [
    item
    for item in bookings
    if query.lower()
    in (
        f"{item.get('id', '')}"
        f"{item.get('passenger', '')}"
    ).lower()
]

render_booking_table(rows)

if bookings:
    with st.container(border=True):
        st.subheader("예약 상태 변경")

        selected = st.selectbox(
            "예약",
            bookings,
            format_func=lambda item: (
                f"{item.get('id')}"
                f" · {item.get('passenger')}"
                f" · {item.get('flight_no', item.get('flight_id', ''))}"
            ),
        )

        current_status = selected.get(
            "status",
            "확정",
        )

        new_status = st.selectbox(
            "변경 상태",
            ["확정", "취소"],
            index=["확정", "취소"].index(current_status),
        )
detail_rows = [
    {"항목": "예약 번호", "내용": selected.get("booking_code")},
    {"항목": "승객명", "내용": selected.get("passenger")},
    {"항목": "항공편", "내용": selected.get("flight_no")},
    {"항목": "좌석", "내용": selected.get("seat_number")},
    {"항목": "현재 상태", "내용": selected.get("status")},
    {"항목": "변경할 상태", "내용": new_status},
    {
        "항목": "금액",
        "내용": f"{selected.get('amount', 0):,}원",
    },
    {
        "항목": "노선",
        "내용": (
            f"{selected.get('origin')} → "
            f"{selected.get('destination')}"
        ),
    },
    {"항목": "출발 일시", "내용": selected.get("departure_at")},
    {"항목": "예약 일시", "내용": selected.get("created_at")},
    {
        "항목": "취소 일시",
        "내용": selected.get("cancelled_at") or "-",
    },
]

st.dataframe(
    pd.DataFrame(detail_rows),
    use_container_width=True,
    hide_index=True,
)