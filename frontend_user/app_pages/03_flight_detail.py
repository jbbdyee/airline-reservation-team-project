import streamlit as st

from clients.flight_client import get_flight_seats
from components.seat_map import render_seat_map

flight = st.session_state.get("selected_flight")

if not flight:
    st.warning("먼저 항공편을 선택해 주세요.")

    st.page_link(
        "app_pages/02_search.py",
        label="항공편 검색으로 이동",
    )

    st.stop()

passengers = flight.get("passengers", 1)
cabin_class = flight.get("cabin_class", "ALL")

cabin_class_name = {
    "ALL": "전체",
    "ECONOMY": "이코노미",
    "BUSINESS": "비즈니스",
}[cabin_class]

st.title("항공편 상세")

first, second, third = st.columns(3)

first.metric(
    "항공편",
    flight["flight_no"],
    flight["airline"],
)

second.metric(
    "출발",
    flight["departure_time"],
    flight["origin"],
)

third.metric(
    "도착",
    flight["arrival_time"],
    flight["destination"],
)

st.write(f"출발일: {flight['departure_date']}")
st.write(f"1인 요금: {flight['price']:,}원")
st.write(f"예약 인원: {passengers}명")
st.write(f"좌석 등급: {cabin_class_name}")

st.subheader("좌석 선택")

render_seat_map(
    get_flight_seats(
        flight["flight_id"],
        cabin_class,
    ),
    passengers,
)

selected_seats = st.session_state.get("selected_seats", [])

if len(selected_seats) == passengers:
    st.success(
        f"선택한 좌석: {', '.join(selected_seats)}"
    )

    if st.button("예약 화면으로 이동", type="primary"):
        if st.session_state.get("user"):
            st.switch_page("app_pages/04_booking.py")
        else:
            st.error(
                "로그인이 필요한 서비스입니다. 로그인 후 예약해 주세요."
            )

            st.page_link(
                "app_pages/01_login.py",
                label="로그인하러 가기",
                icon="🔐",
            )
elif selected_seats:
    remaining = passengers - len(selected_seats)

    st.info(
        f"좌석을 {len(selected_seats)}개 선택했습니다. "
        f"{remaining}개를 더 선택해 주세요."
    )
