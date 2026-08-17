from datetime import date

import streamlit as st
from clients.flight_client import search_flights
from components.flight_card import render_flight_card
from core.api_client import BackendAPIError, request

@st.cache_data(ttl=300)
def get_airports() -> list[dict]:
    """백엔드 API를 통해 Supabase 공항 목록을 조회합니다."""

    airports = request("GET", "/airports")

    if not isinstance(airports, list):
        raise BackendAPIError(
            "공항 목록 응답 형식이 올바르지 않습니다."
        )

    return airports


st.title("항공편 검색")

# 백엔드 → Supabase에서 공항 목록 조회
try:
    airports = get_airports()

except BackendAPIError as error:
    st.error(str(error))
    st.stop()


# Supabase airports 테이블이 비어 있는 경우
if not airports:
    st.warning(
        "등록된 공항이 없습니다. "
        "Supabase의 airports 테이블을 확인해 주세요."
    )
    st.stop()


# IATA 코드를 기준으로 공항 데이터 정리
airport_by_code = {
    airport["iata_code"]: airport
    for airport in airports
}

airport_codes = list(airport_by_code)


def format_airport(code: str) -> str:
    """selectbox에 표시할 공항 이름을 만듭니다."""

    airport = airport_by_code[code]

    return (
        f"{airport['city']} · "
        f"{airport['name']} "
        f"({airport['iata_code']})"
    )


with st.form("search"):
    first, second, third = st.columns(3)
    fourth, fifth, sixth = st.columns(3)

    origin = first.selectbox(
        "출발지",
        airport_codes,
        index=0,
        format_func=format_airport,
    )

    destination = second.selectbox(
        "도착지",
        airport_codes,
        index=1 if len(airport_codes) > 1 else 0,
        format_func=format_airport,
    )

    depart_date = third.date_input(
        "출발일",
        value=date.today(),
        min_value=date.today(),
    )

    passengers = fourth.number_input(
        "인원",
        min_value=1,
        max_value=9,
        value=1,
        step=1,
    )

    cabin_class_label = fifth.selectbox(
        "좌석 등급",
        ["전체", "이코노미", "비즈니스"],
    )

    sort_by = sixth.selectbox(
        "정렬",
        ["가격 낮은 순", "가격 높은 순", "출발 시간 빠른 순"],
    )

    submitted = st.form_submit_button(
        "항공편 검색",
        type="primary",
    )

cabin_class_map = {
    "전체": "ALL",
    "이코노미": "ECONOMY",
    "비즈니스": "BUSINESS",
}

if submitted:
    if origin == destination:
        st.session_state.pop(
            "search_params",
            None,
        )
        st.warning(
            "출발지와 도착지는 서로 다르게 선택해 주세요."
        )

    else:
        st.session_state["search_params"] = {
            "origin": origin,
            "destination": destination,
            "departure_date": depart_date,
            "passengers": int(passengers),
            "cabin_class": cabin_class_map[cabin_class_label],
            "sort_by": sort_by,
        }

search_params = st.session_state.get("search_params")

if search_params:
    results = search_flights(**search_params)

    if results:
        st.subheader(f"검색 결과 {len(results)}건")

        for flight in results:
            render_flight_card(flight)

    else:
        st.info("검색 조건에 맞는 항공편이 없습니다.")

else:
    st.info("검색 조건을 입력한 뒤 항공편 검색을 눌러 주세요.")
