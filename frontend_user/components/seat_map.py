import streamlit as st


def render_seat_map(
    seats: list[dict],
    passengers: int,
) -> None:
    selected_seats = st.session_state.setdefault(
        "selected_seats",
        [],
    )

    st.write(f"선택한 좌석: {len(selected_seats)} / {passengers}석")

    seats_by_row: dict[int, list[dict]] = {}

    for seat in seats:
        row = int(seat["seat_number"][:-1])
        seats_by_row.setdefault(row, []).append(seat)

    for row in sorted(seats_by_row):
        columns = st.columns(4)

        for column, seat in zip(columns, seats_by_row[row]):
            seat_number = seat["seat_number"]
            is_reserved = seat["status"] == "RESERVED"
            is_selected = seat_number in selected_seats

            button_label = (
                f"{seat_number} (선택)"
                if is_selected
                else seat_number
            )

            if column.button(
                button_label,
                key=f"seat_{seat_number}",
                disabled=is_reserved,
                use_container_width=True,
            ):
                if is_selected:
                    selected_seats.remove(seat_number)

                elif len(selected_seats) >= passengers:
                    st.warning(
                        f"인원수만큼({passengers}석)만 선택할 수 있습니다."
                    )

                else:
                    selected_seats.append(seat_number)

                st.rerun()