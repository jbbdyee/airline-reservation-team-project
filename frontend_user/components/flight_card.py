import streamlit as st


def render_flight_card(flight: dict) -> None:
    passengers = flight.get("passengers", 1)
    remaining_seats = flight.get("remaining_seats", 0)
    is_seat_shortage = remaining_seats < passengers

    with st.container(border=True):
        left, middle, right = st.columns([2, 3, 1])

        with left:
            st.subheader(flight["airline"])
            st.write(flight["flight_no"])

        with middle:
            st.write(
                f"{flight['origin']} {flight['departure_time']} "
                f"→ {flight['destination']} {flight['arrival_time']}"
            )
            st.caption(
                f"{flight['departure_date']} · "
                f"잔여 좌석 {remaining_seats}석"
            )

        with right:
            st.write(f"{flight['price']:,}원")
            st.caption("1인 기준")

            if st.button(
                "선택",
                key=f"flight_{flight['flight_id']}",
                disabled=is_seat_shortage,
                use_container_width=True,
            ):
                if not st.session_state.get("user"):
                    st.error(
                        "로그인이 필요한 서비스입니다. 로그인 후 이용해 주세요."
                    )
                    st.page_link(
                        "app_pages/01_login.py",
                        label="로그인하러 가기",
                        icon="🔐",
                    )
                else:
                    st.session_state["selected_flight"] = flight
                    st.session_state.pop("selected_seats", None)
                    st.switch_page("app_pages/03_flight_detail.py")

        if is_seat_shortage:
            st.error(
                "좌석수가 더 적어서 예약이 불가합니다. "
                f"(예약 인원 {passengers}명 / 잔여 좌석 {remaining_seats}석)"
            )