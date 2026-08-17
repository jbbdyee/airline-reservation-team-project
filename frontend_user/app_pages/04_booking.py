import streamlit as st

from clients.booking_client import create_bookings
from components.realtime_status import add_realtime_event
from core.api_client import BackendAPIError
from core.auth import require_login


require_login()

flight = st.session_state.get("selected_flight")
selected_seats = st.session_state.get("selected_seats", [])

if not flight:
    st.warning("먼저 항공편을 선택해 주세요.")

    st.page_link(
        "app_pages/02_search.py",
        label="항공편 검색으로 이동",
    )

    st.stop()

passengers = flight.get("passengers", 1)

if len(selected_seats) != passengers:
    st.warning(
        f"좌석을 {passengers}개 선택한 후 예약할 수 있습니다."
    )

    st.page_link(
        "app_pages/03_flight_detail.py",
        label="좌석 선택으로 이동",
    )

    st.stop()

st.title("예약 확인")

st.write(f"항공편: {flight['flight_no']}")
st.write(f"구간: {flight['origin']} → {flight['destination']}")
st.write(f"출발일: {flight['departure_date']}")
st.write(f"출발 시간: {flight['departure_time']}")
st.write(f"선택 좌석: {', '.join(selected_seats)}")
st.write(f"1인 요금: {flight['price']:,}원")
st.write(f"총 금액: {flight['price'] * passengers:,}원")

st.subheader("승객 정보")

with st.form("booking_form"):
    passenger_details = []

    for index, seat_number in enumerate(selected_seats, start=1):
        passenger_name = st.text_input(
            f"승객 {index} 이름 · 좌석 {seat_number}",
            key=f"passenger_name_{seat_number}",
        )

        passenger_details.append(
            {
                "seat_number": seat_number,
                "name": passenger_name,
            }
        )

    submitted = st.form_submit_button(
        "예약 완료",
        type="primary",
    )

if submitted:
    try:
        bookings = create_bookings(
            user_id=st.session_state["user"]["user_id"],
            flight=flight,
            passenger_details=passenger_details,
        )

        st.session_state["last_bookings"] = bookings
        st.session_state.pop("selected_seats", None)

        booking_numbers = ", ".join(
            str(booking["booking_id"])
            for booking in bookings
        )

        add_realtime_event(
            f"{flight['flight_no']} 항공편 예약이 완료되었습니다. "
            f"(좌석: {', '.join(selected_seats)})"
        )

        st.success(
            f"예약이 완료되었습니다. 예약 번호: {booking_numbers}"
        )

        st.page_link(
            "app_pages/05_my_bookings.py",
            label="내 예약 확인",
        )

    except BackendAPIError as error:
        st.error(str(error))