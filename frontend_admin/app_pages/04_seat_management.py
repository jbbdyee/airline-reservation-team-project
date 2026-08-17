"""항공편별 좌석 조회·생성·수정·삭제 화면."""

import pandas as pd
import streamlit as st

from clients.flight_client import get_flights
from clients.seat_client import (
    create_seat,
    delete_seat,
    get_seats,
    update_seat,
)
from components.seat_form import (
    SEAT_CLASS_LABELS,
    SEAT_CLASS_OPTIONS,
    SEAT_STATUS_LABELS,
    SEAT_STATUS_OPTIONS,
)
from core.api_client import BackendAPIError


st.title("좌석 관리")
st.caption(
    "항공편별 좌석 등급, 가격과 "
    "판매 상태를 관리합니다."
)


# 항공편 조회
try:
    flights = get_flights()

except BackendAPIError as error:
    st.error(str(error))
    st.stop()


if not flights:
    st.info(
        "좌석을 조회할 항공편이 없습니다."
    )
    st.stop()


# 관리할 항공편 선택
flight = st.selectbox(
    "항공편",
    flights,
    format_func=lambda item: (
        f"{item['flight_no']} · "
        f"{item['route']}"
    ),
)


# 선택한 항공편의 좌석 조회
try:
    seats = get_seats(
        flight["id"]
    )

except BackendAPIError as error:
    st.error(str(error))
    st.stop()


# 화면 표시용 좌석 테이블
if seats:
    table_rows = [
        {
            "좌석 번호": seat["seat_number"],
            "좌석 등급": (
                SEAT_CLASS_LABELS.get(
                    seat["cabin_class"],
                    seat["cabin_class"],
                )
            ),
            "가격": seat["price"],
            "상태": (
                SEAT_STATUS_LABELS.get(
                    seat["status"],
                    seat["status"],
                )
            ),
        }
        for seat in seats
    ]

    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info(
        "이 항공편에 등록된 좌석이 없습니다."
    )


edit_tab, create_tab = st.tabs(
    [
        "좌석 수정·삭제",
        "좌석 생성",
    ]
)


# 좌석 수정 및 삭제
with edit_tab:
    if not seats:
        st.info(
            "수정할 좌석이 없습니다."
        )

    else:
        seat = st.selectbox(
            "좌석",
            seats,
            format_func=lambda item: (
                f"{item['seat_number']} · "
                f"{SEAT_CLASS_LABELS.get(
                    item['cabin_class'],
                    item['cabin_class'],
                )} · "
                f"{SEAT_STATUS_LABELS.get(
                    item['status'],
                    item['status'],
                )}"
            ),
        )

        seat_id = seat["id"]
        is_booked = (
            seat["status"] == "BOOKED"
        )

        if is_booked:
            st.warning(
                "예약 완료된 좌석은 관리자 화면에서 "
                "직접 수정하거나 삭제할 수 없습니다."
            )

        column1, column2, column3 = (
            st.columns(3)
        )

        class_codes = list(
            SEAT_CLASS_LABELS
        )

        current_class_index = (
            class_codes.index(
                seat["cabin_class"]
            )
            if seat["cabin_class"]
            in class_codes
            else 0
        )

        edit_cabin_class = (
            column1.selectbox(
                "좌석 등급",
                class_codes,
                index=current_class_index,
                format_func=lambda value: (
                    SEAT_CLASS_LABELS[
                        value
                    ]
                ),
                disabled=is_booked,
                key=(
                    f"edit_class_"
                    f"{seat_id}"
                ),
            )
        )

        edit_price = (
            column2.number_input(
                "가격",
                min_value=1,
                max_value=100_000_000,
                value=int(
                    seat["price"]
                ),
                step=1_000,
                disabled=is_booked,
                key=(
                    f"edit_price_"
                    f"{seat_id}"
                ),
            )
        )

        editable_status_codes = [
            "AVAILABLE",
            "HELD",
        ]

        current_status_index = (
            editable_status_codes.index(
                seat["status"]
            )
            if seat["status"]
            in editable_status_codes
            else 0
        )

        edit_status = (
            column3.selectbox(
                "상태",
                editable_status_codes,
                index=current_status_index,
                format_func=lambda value: (
                    SEAT_STATUS_LABELS[
                        value
                    ]
                ),
                disabled=is_booked,
                key=(
                    f"edit_status_"
                    f"{seat_id}"
                ),
            )
        )

        if st.button(
            "좌석 저장",
            use_container_width=True,
            disabled=is_booked,
            key=f"save_seat_{seat_id}",
        ):
            try:
                update_seat(
                    seat_id,
                    {
                        "cabin_class": (
                            edit_cabin_class
                        ),
                        "price": int(
                            edit_price
                        ),
                        "status": (
                            edit_status
                        ),
                    },
                )

                st.success(
                    "좌석 정보를 변경했습니다."
                )
                st.rerun()

            except BackendAPIError as error:
                st.error(str(error))

        confirm_delete = st.checkbox(
            "선택한 좌석 삭제에 동의합니다.",
            disabled=is_booked,
            key=(
                f"confirm_delete_"
                f"{seat_id}"
            ),
        )

        if st.button(
            "좌석 삭제",
            disabled=(
                is_booked
                or not confirm_delete
            ),
            use_container_width=True,
            key=(
                f"delete_seat_"
                f"{seat_id}"
            ),
        ):
            try:
                delete_seat(
                    seat_id
                )

                st.success(
                    "좌석을 삭제했습니다."
                )
                st.rerun()

            except BackendAPIError as error:
                st.error(str(error))


# 좌석 생성
with create_tab:
    with st.form(
        "seat_create_form",
        clear_on_submit=True,
    ):
        seat_number = st.text_input(
            "좌석 번호",
            placeholder="12A",
            help=(
                "숫자로 된 행 번호와 "
                "영문 대문자 열을 입력하세요."
            ),
        )

        class_label = st.selectbox(
            "좌석 등급",
            list(SEAT_CLASS_OPTIONS),
        )

        price = st.number_input(
            "가격",
            min_value=1,
            max_value=100_000_000,
            value=80_000,
            step=1_000,
        )

        status_label = st.selectbox(
            "초기 상태",
            list(SEAT_STATUS_OPTIONS),
        )

        submitted = (
            st.form_submit_button(
                "좌석 생성",
                use_container_width=True,
            )
        )

    if submitted:
        normalized_seat_number = (
            seat_number
            .strip()
            .upper()
        )

        existing_seat_numbers = {
            item["seat_number"]
            for item in seats
        }

        if not normalized_seat_number:
            st.warning(
                "좌석 번호를 입력해 주세요."
            )

        elif normalized_seat_number in (
            existing_seat_numbers
        ):
            st.warning(
                "같은 항공편에 이미 존재하는 "
                "좌석 번호입니다."
            )

        else:
            try:
                create_seat(
                    flight["id"],
                    {
                        "seat_number": (
                            normalized_seat_number
                        ),
                        "cabin_class": (
                            SEAT_CLASS_OPTIONS[
                                class_label
                            ]
                        ),
                        "price": int(
                            price
                        ),
                        "status": (
                            SEAT_STATUS_OPTIONS[
                                status_label
                            ]
                        ),
                    },
                )

                st.success(
                    "좌석을 생성했습니다."
                )
                st.rerun()

            except BackendAPIError as error:
                st.error(str(error))