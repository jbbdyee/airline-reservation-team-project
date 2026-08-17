import streamlit as st

from core.date_time import format_datetime


def render_booking_card(booking: dict) -> tuple[bool, str]:

    booking_id = booking["booking_id"]
    show_reason_key = f"show_cancel_reason_{booking_id}"

    with st.container(border=True):
        st.subheader(
            f"{booking['flight_no']} · {booking['route']}"
        )

        st.write(
            f"{booking['departure_date']} "
            f"{booking['departure_time']} · "
            f"좌석 {booking['seat_number']}"
        )

        st.write(
            f"승객: {booking.get('passenger_name', '정보 없음')}"
        )

        st.caption(
            f"예약 번호: {booking['booking_id']} · "
            f"생성: {format_datetime(booking['created_at'])}"
        )

        if booking["status"] == "CANCELLED":
            st.error("취소됨")
            st.write(
                f"취소 사유: {booking.get('cancel_reason', '')}"
            )

            if booking.get("cancelled_at"):
                st.caption(
                    "취소 시각: "
                    f"{format_datetime(booking['cancelled_at'])}"
                )

            return False, ""

        # 처음에는 취소 버튼만 보인다.
        if not st.session_state.get(show_reason_key, False):
            if st.button(
                "예약 취소",
                key=f"show_cancel_button_{booking_id}",
            ):
                st.session_state[show_reason_key] = True

        # 예약 취소 버튼을 누른 뒤에만 입력창을 보여 준다.
        if st.session_state.get(show_reason_key, False):
            with st.form(f"cancel_form_{booking_id}"):
                reason = st.text_input(
                    "취소 사유",
                    key=f"reason_{booking_id}",
                    max_chars=300,
                    placeholder="취소 사유를 입력해 주세요.",
                )

                submitted = st.form_submit_button(
                    "취소 확정",
                    type="primary",
                )

            return submitted, reason

        return False, ""