"""관리자 운영 대시보드 화면."""

import pandas as pd
import streamlit as st

from clients.dashboard_client import (
    get_dashboard,
)
from core.api_client import BackendAPIError
from core.auth import is_admin


# 관리자 권한 확인
if not is_admin():
    st.warning(
        "관리자 로그인이 필요합니다."
    )
    st.stop()


st.title("운영 대시보드")

st.caption(
    "항공편, 예약, 매출, 챗봇 평가와 "
    "최근 운영 이벤트를 확인합니다."
)


# 실제 백엔드 대시보드 조회
try:
    dashboard = get_dashboard()

except BackendAPIError as error:
    st.error(str(error))
    st.stop()


# 백엔드 중첩 응답 분리
flight_metrics = dashboard.get(
    "flights",
    {},
)

booking_metrics = dashboard.get(
    "bookings",
    {},
)

chat_metrics = dashboard.get(
    "chat_feedbacks",
    {},
)

recent_events = dashboard.get(
    "recent_events",
    [],
)


# None이 반환될 수 있는 평균 평점 처리
average_rating = (
    chat_metrics.get(
        "average_rating"
    )
    or 0
)

# 백엔드는 0~1 비율로 반환하므로
# 화면에서는 100을 곱해서 백분율로 표시
low_rating_ratio = (
    chat_metrics.get(
        "low_rating_ratio",
        0,
    )
    * 100
)

confirmed_revenue = (
    booking_metrics.get(
        "confirmed_revenue",
        0,
    )
)


# 주요 지표
st.subheader("주요 운영 지표")

metric_columns = st.columns(5)

metric_columns[0].metric(
    "전체 항공편",
    (
        f"{flight_metrics.get('total', 0):,}편"
    ),
)

metric_columns[1].metric(
    "운항 예정",
    (
        f"{flight_metrics.get('scheduled', 0):,}편"
    ),
)

metric_columns[2].metric(
    "확정 예약",
    (
        f"{booking_metrics.get('confirmed', 0):,}건"
    ),
)

metric_columns[3].metric(
    "확정 예약 매출",
    f"{confirmed_revenue:,}원",
)

metric_columns[4].metric(
    "챗봇 평균 평점",
    f"{average_rating:.2f} / 5",
)


st.divider()


# 항공편 및 예약 현황
flight_column, booking_column = (
    st.columns(2)
)


with flight_column:
    st.subheader("항공편 운항 현황")

    flight_chart = pd.DataFrame(
        {
            "상태": [
                "운항 예정",
                "지연",
                "결항",
                "출발",
            ],
            "항공편 수": [
                flight_metrics.get(
                    "scheduled",
                    0,
                ),
                flight_metrics.get(
                    "delayed",
                    0,
                ),
                flight_metrics.get(
                    "cancelled",
                    0,
                ),
                flight_metrics.get(
                    "departed",
                    0,
                ),
            ],
        }
    ).set_index("상태")

    st.bar_chart(
        flight_chart,
        color="#0EA5E9",
    )

    flight_status_columns = (
        st.columns(4)
    )

    flight_status_columns[0].metric(
        "예정",
        flight_metrics.get(
            "scheduled",
            0,
        ),
    )

    flight_status_columns[1].metric(
        "지연",
        flight_metrics.get(
            "delayed",
            0,
        ),
    )

    flight_status_columns[2].metric(
        "결항",
        flight_metrics.get(
            "cancelled",
            0,
        ),
    )

    flight_status_columns[3].metric(
        "출발",
        flight_metrics.get(
            "departed",
            0,
        ),
    )


with booking_column:
    st.subheader("예약 현황")

    booking_chart = pd.DataFrame(
        {
            "상태": [
                "확정",
                "취소",
            ],
            "예약 수": [
                booking_metrics.get(
                    "confirmed",
                    0,
                ),
                booking_metrics.get(
                    "cancelled",
                    0,
                ),
            ],
        }
    ).set_index("상태")

    st.bar_chart(
        booking_chart,
        color="#38BDF8",
    )

    booking_status_columns = (
        st.columns(3)
    )

    booking_status_columns[0].metric(
        "전체",
        booking_metrics.get(
            "total",
            0,
        ),
    )

    booking_status_columns[1].metric(
        "확정",
        booking_metrics.get(
            "confirmed",
            0,
        ),
    )

    booking_status_columns[2].metric(
        "취소",
        booking_metrics.get(
            "cancelled",
            0,
        ),
    )


st.divider()


# 챗봇 평가
st.subheader("챗봇 평가 현황")

chat_metric_columns = st.columns(4)

chat_metric_columns[0].metric(
    "평균 평점",
    f"{average_rating:.2f}",
)

chat_metric_columns[1].metric(
    "전체 평가",
    (
        f"{chat_metrics.get('total_count', 0):,}건"
    ),
)

chat_metric_columns[2].metric(
    "저평점 평가",
    (
        f"{chat_metrics.get(
            'low_rating_count',
            0,
        ):,}건"
    ),
)

chat_metric_columns[3].metric(
    "저평점 비율",
    f"{low_rating_ratio:.1f}%",
)


rating_counts = chat_metrics.get(
    "rating_counts",
    {},
)


def get_rating_count(
    score: int,
) -> int:
    """JSON의 문자열 키와 정수 키를 모두 처리합니다."""

    return rating_counts.get(
        score,
        rating_counts.get(
            str(score),
            0,
        ),
    )


rating_chart = pd.DataFrame(
    {
        "평점": [
            f"{score}점"
            for score in range(
                1,
                6,
            )
        ],
        "평가 수": [
            get_rating_count(score)
            for score in range(
                1,
                6,
            )
        ],
    }
).set_index("평점")


st.bar_chart(
    rating_chart,
    color="#0284C7",
)


st.divider()


# 최근 이벤트
st.subheader("최근 이벤트")

if not recent_events:
    st.info(
        "최근 운영 이벤트가 없습니다."
    )

else:
    event_type_labels = {
        "FLIGHT_STATUS_CHANGED": (
            "항공편 상태 변경"
        ),
        "SEAT_CHANGED": (
            "좌석 변경"
        ),
        "BOOKING_CHANGED": (
            "예약 변경"
        ),
    }

    event_rows = [
        {
            "이벤트 ID": event.get(
                "id"
            ),
            "유형": (
                event_type_labels.get(
                    event.get(
                        "event_type"
                    ),
                    event.get(
                        "event_type",
                        "",
                    ),
                )
            ),
            "리소스 ID": event.get(
                "resource_id"
            ),
            "항공편 ID": event.get(
                "flight_id"
            ),
            "예약 ID": event.get(
                "booking_id"
            ),
            "처리자 ID": event.get(
                "actor_user_id"
            ),
            "발생 시각": event.get(
                "created_at"
            ),
        }
        for event in recent_events
    ]

    st.dataframe(
        pd.DataFrame(
            event_rows
        ),
        use_container_width=True,
        hide_index=True,
    )

    selected_event_id = st.selectbox(
        "이벤트 상세",
        [
            event["id"]
            for event in recent_events
        ],
        format_func=lambda event_id: (
            f"이벤트 #{event_id}"
        ),
    )

    selected_event = next(
        event
        for event in recent_events
        if event["id"]
        == selected_event_id
    )

    with st.expander(
        "이벤트 payload 확인",
        expanded=False,
    ):

        payload = selected_event.get("payload", {})

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
        else:
            st.info("표시할 payload 정보가 없습니다.")
