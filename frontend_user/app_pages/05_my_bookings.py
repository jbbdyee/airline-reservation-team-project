import streamlit as st

from clients.booking_client import cancel_booking, get_my_bookings
from components.booking_card import render_booking_card
from components.realtime_status import (
    add_realtime_event,
    render_realtime_status,
)
from core.api_client import BackendAPIError
from core.auth import require_login


require_login()

st.title("내 예약")

render_realtime_status()

bookings = get_my_bookings(
    st.session_state["user"]["user_id"]
)

if not bookings:
    st.info("아직 예약한 항공편이 없습니다.")

for booking in bookings:
    submitted, reason = render_booking_card(booking)

    if submitted:
        try:
            cancel_booking(
                user_id=st.session_state["user"]["user_id"],
                booking_id=booking["booking_id"],
                reason=reason,
            )

            add_realtime_event(
                f"{booking['flight_no']} 항공편 예약을 취소했습니다. "
                f"(좌석: {booking['seat_number']})"
            )

            st.success("예약을 취소했습니다.")
            st.rerun()

        except BackendAPIError as error:
            st.error(str(error))