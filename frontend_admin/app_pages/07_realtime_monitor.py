"""관리자 실시간 이벤트 모니터 화면."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import streamlit as st

from clients.event_client import (
    get_event_log,
    get_event_logs,
)
from components.realtime_log import (
    render_event_detail,
    render_realtime_table,
)
from core.api_client import BackendAPIError


EVENT_TYPE_OPTIONS = {
    "전체": None,
    "운항 상태 변경": "FLIGHT_STATUS_CHANGED",
    "좌석 변경": "SEAT_CHANGED",
    "예약 변경": "BOOKING_CHANGED",
}


def reset_page() -> None:
    st.session_state["event_page"] = 1


def validate_uuid(
    value: str,
    field_name: str,
) -> str | None:
    """입력된 문자열이 UUID인지 검증합니다."""

    normalized = value.strip()

    if not normalized:
        return None

    try:
        return str(UUID(normalized))
    except ValueError:
        st.error(f"{field_name}는 올바른 UUID 형식이어야 합니다.")
        st.stop()


def make_date_range(
    start_date: date,
    end_date: date,
) -> tuple[str, str]:
    """
    한국 시간 기준 시작일과 종료일을 UTC offset이 포함된 문자열로 만듭니다.
    """

    korea_timezone = ZoneInfo("Asia/Seoul")

    start_datetime = datetime.combine(
        start_date,
        time.min,
        tzinfo=korea_timezone,
    )

    end_datetime = datetime.combine(
        end_date,
        time.max,
        tzinfo=korea_timezone,
    )

    return (
        start_datetime.isoformat(),
        end_datetime.isoformat(),
    )


st.title("실시간 모니터")
st.caption(
    "Supabase 이벤트 로그를 주기적으로 조회하여 "
    "운항·예약·좌석 변경 사항을 확인합니다."
)

if "event_page" not in st.session_state:
    st.session_state["event_page"] = 1

filter_column, flight_column, booking_column = st.columns(3)

selected_event_label = filter_column.selectbox(
    "이벤트 유형",
    list(EVENT_TYPE_OPTIONS),
    key="event_type_filter",
    on_change=reset_page,
)

flight_id_input = flight_column.text_input(
    "항공편 ID",
    placeholder="UUID 형식",
    on_change=reset_page,
)

booking_id_input = booking_column.text_input(
    "예약 ID",
    placeholder="UUID 형식",
    on_change=reset_page,
)

date_column1, date_column2, size_column = st.columns([2, 2, 1])

start_date = date_column1.date_input(
    "시작일",
    value=date.today() - timedelta(days=7),
    on_change=reset_page,
)

end_date = date_column2.date_input(
    "종료일",
    value=date.today(),
    on_change=reset_page,
)

page_size = size_column.selectbox(
    "페이지당 개수",
    [10, 20, 50, 100],
    index=1,
    key="event_page_size",
    on_change=reset_page,
)

control_column1, control_column2 = st.columns([2, 1])

auto_refresh = control_column1.toggle(
    "3초마다 자동 갱신",
    value=True,
)

if control_column2.button(
    "지금 새로고침",
    use_container_width=True,
):
    st.rerun()

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

flight_id = validate_uuid(
    flight_id_input,
    "항공편 ID",
)

booking_id = validate_uuid(
    booking_id_input,
    "예약 ID",
)

start_at, end_at = make_date_range(
    start_date,
    end_date,
)

selected_event_type = EVENT_TYPE_OPTIONS[selected_event_label]


@st.fragment(run_every=3.0 if auto_refresh else None)
def render_monitor() -> None:
    """이벤트 로그 영역을 자동으로 갱신합니다."""

    page = st.session_state["event_page"]

    try:
        result = get_event_logs(
            event_type=selected_event_type,
            flight_id=flight_id,
            booking_id=booking_id,
            start_at=start_at,
            end_at=end_at,
            page=page,
            page_size=page_size,
        )
    except BackendAPIError as error:
        st.error(str(error))
        return

    events = result["items"]
    total = result["total"]
    total_pages = result["total_pages"]

    if total_pages > 0 and page > total_pages:
        st.session_state["event_page"] = total_pages
        st.rerun()
        return

    metric_column1, metric_column2, metric_column3 = st.columns(3)

    metric_column1.metric(
        "조회 이벤트",
        f"{total:,}건",
    )

    metric_column2.metric(
        "현재 페이지",
        f"{page} / {max(total_pages, 1)}",
    )

    metric_column3.metric(
        "갱신 방식",
        "자동 3초" if auto_refresh else "수동",
    )

    render_realtime_table(events)

    previous_column, page_column, next_column = st.columns([1, 2, 1])

    with previous_column:
        if st.button(
            "이전 페이지",
            key="event_previous_page",
            disabled=page <= 1,
            use_container_width=True,
        ):
            st.session_state["event_page"] = page - 1
            st.rerun()

    with page_column:
        st.markdown(
            (
                "<div style='text-align:center; padding-top:8px;'>"
                f"{page} / {max(total_pages, 1)} 페이지"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    with next_column:
        if st.button(
            "다음 페이지",
            key="event_next_page",
            disabled=total_pages == 0 or page >= total_pages,
            use_container_width=True,
        ):
            st.session_state["event_page"] = page + 1
            st.rerun()

    if not events:
        return

    st.divider()

    with st.container(border=True):
        st.subheader("이벤트 상세")

        selected_event = st.selectbox(
            "이벤트 선택",
            events,
            format_func=lambda event: (
                f"#{event.get('id', '')}"
                f" · {event.get('created_at', '')}"
                f" · {event.get('event_label', '')}"
                f" · {event.get('summary', '')}"
            ),
            key="selected_event",
        )

        try:
            detail = get_event_log(selected_event["id"])
        except BackendAPIError as error:
            st.error(str(error))
        else:
            render_event_detail(detail)


render_monitor()