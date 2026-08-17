"""실시간 이벤트 목록 및 상세 컴포넌트."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st


def render_realtime_table(events: list[dict]) -> None:
    """이벤트 로그 목록을 테이블로 표시합니다."""

    if not events:
        st.info("조회된 이벤트 로그가 없습니다.")
        return

    table_rows = [
        {
            "이벤트 ID": event.get("id", ""),
            "발생 시각": event.get("created_at", "-"),
            "이벤트 유형": event.get(
                "event_label",
                event.get("event_type", ""),
            ),
            "요약": event.get("summary", ""),
            "항공편 ID": event.get("flight_id") or "-",
            "예약 ID": event.get("booking_id") or "-",
            "처리 사용자": event.get("actor_user_id") or "-",
        }
        for event in events
    ]

    dataframe = pd.DataFrame(table_rows)

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "이벤트 ID": st.column_config.NumberColumn(
                "이벤트 ID",
                format="%d",
                width="small",
            ),
            "발생 시각": st.column_config.TextColumn(
                "발생 시각",
                width="medium",
            ),
            "이벤트 유형": st.column_config.TextColumn(
                "이벤트 유형",
                width="medium",
            ),
            "요약": st.column_config.TextColumn(
                "요약",
                width="large",
            ),
            "항공편 ID": st.column_config.TextColumn(
                "항공편 ID",
                width="medium",
            ),
            "예약 ID": st.column_config.TextColumn(
                "예약 ID",
                width="medium",
            ),
            "처리 사용자": st.column_config.TextColumn(
                "처리 사용자",
                width="medium",
            ),
        },
    )


def render_event_detail(event: dict) -> None:
    """선택한 이벤트의 상세 내용을 표시합니다."""

    if not event:
        st.info("이벤트 상세 정보가 없습니다.")
        return

    first_column, second_column = st.columns(2)

    with first_column:
        st.write(f"이벤트 ID: `{event.get('id', '-')}`")
        st.write(
            "이벤트 유형: "
            f"{event.get('event_label', event.get('event_type', '-'))}"
        )
        st.write(f"발생 시각: {event.get('created_at', '-')}")

    with second_column:
        st.write(f"리소스 ID: `{event.get('resource_id', '-')}`")
        st.write(f"항공편 ID: `{event.get('flight_id') or '-'}`")
        st.write(f"예약 ID: `{event.get('booking_id') or '-'}`")
        st.write(f"처리 사용자: `{event.get('actor_user_id') or '-'}`")

    st.write(f"요약: {event.get('summary', '-')}")

    st.markdown("#### Payload")

    payload = event.get("payload", {})

    if isinstance(payload, dict) and payload:
        payload_rows = [
        {"항목": key, "내용": value}
        for key, value in payload.items()
    ]

        st.dataframe(
        pd.DataFrame(payload_rows),
        use_container_width=True,
        hide_index=True,
    )
    elif not payload:
        st.info("표시할 Payload 정보가 없습니다.")
    else:
        st.write(payload)