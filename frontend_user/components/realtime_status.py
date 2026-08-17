from datetime import datetime

import streamlit as st

from core.date_time import format_datetime


def add_realtime_event(message: str) -> None:
    """예약 또는 취소 이벤트를 현재 세션에 기록합니다."""

    events = st.session_state.setdefault("mock_events", [])

    events.append(
        {
            "created_at": datetime.now(),
            "message": message,
        }
    )


def render_realtime_status() -> None:
    """최근 예약·취소 상태 변경을 표시합니다."""

    events = st.session_state.get("mock_events", [])

    st.subheader("최근 상태 변경")

    if not events:
        st.info("아직 예약 또는 취소 이벤트가 없습니다.")
        return

    latest_events = events[-5:]

    for event in reversed(latest_events):
        st.write(
            f"[{format_datetime(event['created_at'])}] "
            f"{event['message']}"
        )