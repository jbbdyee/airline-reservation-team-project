"""실제 백엔드와 연동된 항공편 관리 화면."""

from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

import streamlit as st

from clients.airport_client import get_airports
from clients.flight_client import (
    create_flight,
    delete_flight,
    get_flights,
    update_flight,
)
from components.flight_table import render_flight_table
from core.api_client import BackendAPIError


KST = ZoneInfo("Asia/Seoul")

STATUS_OPTIONS = {
    "정상": "SCHEDULED",
    "지연": "DELAYED",
    "결항": "CANCELLED",
    "출발": "DEPARTED",
}

STATUS_LABELS = {
    value: label
    for label, value in STATUS_OPTIONS.items()
}


def parse_backend_datetime(
    value: str,
) -> datetime:
    normalized = value.replace(
        "Z",
        "+00:00",
    )

    parsed = datetime.fromisoformat(
        normalized
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(KST)


def combine_kst_datetime(
    selected_date: date,
    selected_time: time,
) -> datetime:
    return datetime.combine(
        selected_date,
        selected_time,
        tzinfo=KST,
    )


def format_airport(
    airport: dict,
) -> str:
    return (
        f"{airport['city']} · "
        f"{airport['name']} "
        f"({airport['iata_code']})"
    )


st.title("항공편 관리")
st.caption(
    "Supabase에 저장된 항공편을 "
    "조회·등록·수정·삭제합니다."
)


# 공항 및 항공편 조회
try:
    airports = get_airports()
    flights = get_flights()

except BackendAPIError as error:
    st.error(str(error))
    st.stop()


if len(airports) < 2:
    st.warning(
        "항공편을 등록하려면 공항이 "
        "2개 이상 필요합니다."
    )
    st.stop()


airport_index_by_id = {
    airport["id"]: index
    for index, airport in enumerate(airports)
}


# 검색 영역
keyword = st.text_input(
    "항공편 검색",
    placeholder="편명 또는 노선",
)

normalized_keyword = (
    keyword.strip().lower()
)

filtered_flights = [
    flight
    for flight in flights
    if normalized_keyword
    in (
        f"{flight['flight_no']} "
        f"{flight['route']}"
    ).lower()
]


# 테이블에는 화면에 필요한 필드만 표시
table_rows = [
    {
        "편명": flight["flight_no"],
        "노선": flight["route"],
        "출발": flight["departure"],
        "도착": flight["arrival"],
        "상태": flight["status"],
        "기본 가격": flight["base_price"],
        "최저 좌석 가격": flight[
            "lowest_seat_price"
        ],
        "예약 가능 좌석": flight[
            "available_seats"
        ],
    }
    for flight in filtered_flights
]

render_flight_table(table_rows)


edit_column, create_column = st.columns(2)


# 항공편 수정·삭제
with edit_column:
    with st.container(border=True):
        st.subheader("항공편 수정·삭제")

        if not flights:
            st.info(
                "등록된 항공편이 없습니다."
            )

        else:
            selected = st.selectbox(
                "항공편",
                flights,
                format_func=lambda flight: (
                    f"{flight['flight_no']} · "
                    f"{flight['route']}"
                ),
            )

            selected_id = selected["id"]

            current_departure = (
                parse_backend_datetime(
                    selected["departure_at"]
                )
            )
            current_arrival = (
                parse_backend_datetime(
                    selected["arrival_at"]
                )
            )

            edit_flight_number = st.text_input(
                "편명",
                value=selected["flight_no"],
                key=(
                    f"edit_number_"
                    f"{selected_id}"
                ),
            )

            edit_origin = st.selectbox(
                "출발 공항",
                airports,
                index=airport_index_by_id.get(
                    selected[
                        "origin_airport_id"
                    ],
                    0,
                ),
                format_func=format_airport,
                key=(
                    f"edit_origin_"
                    f"{selected_id}"
                ),
            )

            edit_destination = st.selectbox(
                "도착 공항",
                airports,
                index=airport_index_by_id.get(
                    selected[
                        "destination_airport_id"
                    ],
                    1,
                ),
                format_func=format_airport,
                key=(
                    f"edit_destination_"
                    f"{selected_id}"
                ),
            )

            edit_departure_date = st.date_input(
                "출발 날짜",
                value=current_departure.date(),
                key=(
                    f"edit_departure_date_"
                    f"{selected_id}"
                ),
            )

            edit_departure_time = st.time_input(
                "출발 시간",
                value=current_departure.time(),
                key=(
                    f"edit_departure_time_"
                    f"{selected_id}"
                ),
            )

            edit_arrival_date = st.date_input(
                "도착 날짜",
                value=current_arrival.date(),
                key=(
                    f"edit_arrival_date_"
                    f"{selected_id}"
                ),
            )

            edit_arrival_time = st.time_input(
                "도착 시간",
                value=current_arrival.time(),
                key=(
                    f"edit_arrival_time_"
                    f"{selected_id}"
                ),
            )

            current_status_code = selected[
                "status_code"
            ]

            edit_status = st.selectbox(
                "운항 상태",
                list(STATUS_OPTIONS),
                index=list(
                    STATUS_OPTIONS.values()
                ).index(
                    current_status_code
                ),
                key=(
                    f"edit_status_"
                    f"{selected_id}"
                ),
            )

            edit_base_price = st.number_input(
                "기본 가격",
                min_value=1,
                max_value=100_000_000,
                value=int(
                    selected["base_price"]
                ),
                step=1_000,
                key=(
                    f"edit_price_"
                    f"{selected_id}"
                ),
            )

            if st.button(
                "항공편 수정",
                use_container_width=True,
                key=(
                    f"update_flight_"
                    f"{selected_id}"
                ),
            ):
                departure_at = (
                    combine_kst_datetime(
                        edit_departure_date,
                        edit_departure_time,
                    )
                )

                arrival_at = (
                    combine_kst_datetime(
                        edit_arrival_date,
                        edit_arrival_time,
                    )
                )

                if (
                    edit_origin["id"]
                    == edit_destination["id"]
                ):
                    st.warning(
                        "출발 공항과 도착 공항은 "
                        "서로 달라야 합니다."
                    )

                elif arrival_at <= departure_at:
                    st.warning(
                        "도착 일시는 출발 일시보다 "
                        "늦어야 합니다."
                    )

                elif not edit_flight_number.strip():
                    st.warning(
                        "편명을 입력해 주세요."
                    )

                else:
                    try:
                        update_flight(
                            selected_id,
                            {
                                "flight_number": (
                                    edit_flight_number
                                    .strip()
                                    .upper()
                                ),
                                "origin_airport_id": (
                                    edit_origin["id"]
                                ),
                                "destination_airport_id": (
                                    edit_destination[
                                        "id"
                                    ]
                                ),
                                "departure_at": (
                                    departure_at
                                    .isoformat()
                                ),
                                "arrival_at": (
                                    arrival_at
                                    .isoformat()
                                ),
                                "status": (
                                    STATUS_OPTIONS[
                                        edit_status
                                    ]
                                ),
                                "base_price": int(
                                    edit_base_price
                                ),
                            },
                        )

                        st.success(
                            "항공편 정보를 수정했습니다."
                        )
                        st.rerun()

                    except BackendAPIError as error:
                        st.error(str(error))

            confirm_delete = st.checkbox(
                "선택한 항공편 삭제에 동의합니다.",
                key=(
                    f"confirm_delete_"
                    f"{selected_id}"
                ),
            )

            if st.button(
                "항공편 삭제",
                disabled=not confirm_delete,
                use_container_width=True,
                key=(
                    f"delete_flight_"
                    f"{selected_id}"
                ),
            ):
                try:
                    delete_flight(
                        selected_id
                    )

                    st.success(
                        "항공편을 삭제했습니다."
                    )
                    st.rerun()

                except BackendAPIError as error:
                    st.error(str(error))


# 항공편 등록
with create_column:
    with st.container(border=True):
        st.subheader("항공편 등록")

        tomorrow = (
            date.today()
            + timedelta(days=1)
        )

        with st.form(
            "flight_create_form",
            clear_on_submit=True,
        ):
            flight_number = st.text_input(
                "편명",
                placeholder="KE101",
            )

            origin = st.selectbox(
                "출발 공항",
                airports,
                index=0,
                format_func=format_airport,
            )

            destination = st.selectbox(
                "도착 공항",
                airports,
                index=1,
                format_func=format_airport,
            )

            departure_date = st.date_input(
                "출발 날짜",
                value=tomorrow,
                min_value=date.today(),
            )

            departure_time = st.time_input(
                "출발 시간",
                value=time(9, 0),
            )

            arrival_date = st.date_input(
                "도착 날짜",
                value=tomorrow,
                min_value=date.today(),
            )

            arrival_time = st.time_input(
                "도착 시간",
                value=time(10, 30),
            )

            status_label = st.selectbox(
                "운항 상태",
                list(STATUS_OPTIONS),
                index=0,
            )

            base_price = st.number_input(
                "기본 가격",
                min_value=1,
                max_value=100_000_000,
                value=80_000,
                step=1_000,
            )

            submitted = (
                st.form_submit_button(
                    "항공편 등록",
                    use_container_width=True,
                )
            )

        if submitted:
            departure_at = (
                combine_kst_datetime(
                    departure_date,
                    departure_time,
                )
            )

            arrival_at = (
                combine_kst_datetime(
                    arrival_date,
                    arrival_time,
                )
            )

            if not flight_number.strip():
                st.warning(
                    "편명을 입력해 주세요."
                )

            elif origin["id"] == destination["id"]:
                st.warning(
                    "출발 공항과 도착 공항은 "
                    "서로 달라야 합니다."
                )

            elif arrival_at <= departure_at:
                st.warning(
                    "도착 일시는 출발 일시보다 "
                    "늦어야 합니다."
                )

            else:
                try:
                    create_flight(
                        {
                            "flight_number": (
                                flight_number
                                .strip()
                                .upper()
                            ),
                            "origin_airport_id": (
                                origin["id"]
                            ),
                            "destination_airport_id": (
                                destination["id"]
                            ),
                            "departure_at": (
                                departure_at
                                .isoformat()
                            ),
                            "arrival_at": (
                                arrival_at
                                .isoformat()
                            ),
                            "status": (
                                STATUS_OPTIONS[
                                    status_label
                                ]
                            ),
                            "base_price": int(
                                base_price
                            ),
                        }
                    )

                    st.success(
                        "항공편을 등록했습니다."
                    )
                    st.rerun()

                except BackendAPIError as error:
                    st.error(str(error))