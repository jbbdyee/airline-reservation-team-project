"""백엔드 확정 전 UI 시연을 위한 세션 기반 데이터 저장소."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import streamlit as st


SEED = {
    "flights": [
        {"id":"FL-101","flight_no":"KE101","route":"서울(ICN) → 제주(CJU)","departure":"2026-08-08 08:30","arrival":"2026-08-08 09:40","aircraft":"B737-8","status":"정상","seats":189},
        {"id":"FL-205","flight_no":"OZ205","route":"서울(GMP) → 부산(PUS)","departure":"2026-08-08 10:10","arrival":"2026-08-08 11:15","aircraft":"A321","status":"지연","seats":174},
        {"id":"FL-330","flight_no":"KE330","route":"제주(CJU) → 서울(GMP)","departure":"2026-08-08 13:00","arrival":"2026-08-08 14:10","aircraft":"B737-9","status":"탑승중","seats":189},
    ],
    "seats": [
        {"id":"ST-1","flight_no":"KE101","seat_number":"1A","class":"비즈니스","price":210000,"status":"예약 가능"},
        {"id":"ST-2","flight_no":"KE101","seat_number":"1B","class":"비즈니스","price":210000,"status":"예약 완료"},
        {"id":"ST-3","flight_no":"KE101","seat_number":"12A","class":"이코노미","price":89000,"status":"예약 가능"},
        {"id":"ST-4","flight_no":"OZ205","seat_number":"8C","class":"이코노미","price":72000,"status":"점검 중"},
    ],
    "bookings": [
        {"id":"BK-24081","passenger":"김민준","flight_no":"KE101","seat_number":"1B","amount":210000,"status":"확정","created_at":"2026-08-07 09:22"},
        {"id":"BK-24082","passenger":"이서연","flight_no":"OZ205","seat_number":"8A","amount":72000,"status":"확정","created_at":"2026-08-07 10:05"},
        {"id":"BK-24083","passenger":"박지훈","flight_no":"KE330","seat_number":"15F","amount":94000,"status":"취소","created_at":"2026-08-07 10:31"},
    ],
    "users": [
        {"id":"U-1001","name":"김민준","email":"minjun@example.com","role":"user","status":"활성","joined":"2026-07-15"},
        {"id":"U-1002","name":"이서연","email":"seoyeon@example.com","role":"user","status":"활성","joined":"2026-07-19"},
        {"id":"U-0001","name":"TK 관리자","email":"admin@skyops.dev","role":"admin","status":"활성","joined":"2026-06-01"},
    ],
    "events": [
        {"id":"EV-901","type":"FLIGHT_STATUS_CHANGED","target_id":"FL-205","summary":"OZ205 운항 상태가 지연으로 변경됨","occurred_at":"2026-08-07 10:42:18","actor":"admin@skyops.dev","payload":{"before":"정상","after":"지연","reason":"연결편 도착 지연"}},
        {"id":"EV-902","type":"BOOKING_CREATED","target_id":"BK-24082","summary":"OZ205 8A 좌석 예약 생성","occurred_at":"2026-08-07 10:05:11","actor":"seoyeon@example.com","payload":{"flight_no":"OZ205","seat_number":"8A"}},
        {"id":"EV-903","type":"BOOKING_CANCELLED","target_id":"BK-24083","summary":"KE330 15F 예약 취소","occurred_at":"2026-08-07 10:31:04","actor":"jihoon@example.com","payload":{"refund":94000}},
        {"id":"EV-904","type":"SEAT_CHANGED","target_id":"BK-24081","summary":"KE101 좌석 1A에서 1B로 변경","occurred_at":"2026-08-07 09:55:32","actor":"admin@skyops.dev","payload":{"before":"1A","after":"1B"}},
    ],
    "feedbacks": [
        {"id":"FB-001","conversation_id":"CV-8A21","rating":1,"question":"오늘 제주행 최저가 항공편이 뭐야?","answer":"현재 확인 가능한 항공편이 없습니다.","comment":"검색 결과에는 있는데 없다고 답했어요.","created_at":"2026-08-07 09:10","cause":"부정확","memo":"항공편 검색 API 결과와 답변 grounding 확인"},
        {"id":"FB-002","conversation_id":"CV-7D19","rating":2,"question":"예약 취소 수수료를 알려줘","answer":"예약은 마이페이지에서 취소할 수 있습니다.","comment":"수수료를 물었는데 취소 방법만 알려줌","created_at":"2026-08-06 16:42","cause":"질문 이해 실패","memo":"수수료 정책 FAQ 우선 검색"},
        {"id":"FB-003","conversation_id":"CV-5C44","rating":5,"question":"좌석 변경 방법 알려줘","answer":"마이페이지의 예약 상세에서 좌석 변경을 선택하세요.","comment":"빠르고 정확해요","created_at":"2026-08-06 11:08","cause":"","memo":""},
        {"id":"FB-004","conversation_id":"CV-2B11","rating":2,"question":"유아 동반 수하물 규정은?","answer":"항공편마다 수하물 규정이 다릅니다.","comment":"정보가 너무 부족합니다.","created_at":"2026-08-05 14:30","cause":"정보 부족","memo":"유아 수하물 규정 문서 추가"},
        {"id":"FB-005","conversation_id":"CV-9F20","rating":4,"question":"김포공항 체크인 시간은?","answer":"국내선은 출발 30분 전까지 체크인을 완료해 주세요.","comment":"","created_at":"2026-08-04 08:01","cause":"","memo":""},
    ],
    "service_feedbacks": [
        {"id":"SF-001","user_id":"U-1001","rating":5,"category":"예약","content":"좌석 선택과 예약 과정이 편리했습니다.","created_at":"2026-08-07 11:20"},
        {"id":"SF-002","user_id":"U-1002","rating":3,"category":"검색","content":"가격 정렬 조건이 더 다양하면 좋겠습니다.","created_at":"2026-08-06 15:10"},
        {"id":"SF-003","user_id":"U-1001","rating":2,"category":"실시간 알림","content":"지연 상태 반영이 늦게 보였습니다.","created_at":"2026-08-05 18:45"},
    ],
}


def store() -> dict:
    if "demo_store" not in st.session_state:
        st.session_state.demo_store = deepcopy(SEED)
    return st.session_state.demo_store


def next_id(collection: str, prefix: str) -> str:
    """삭제 후 다시 생성해도 중복되지 않는 데모 ID를 반환합니다."""

    numbers = []
    for item in store()[collection]:
        try:
            numbers.append(int(item["id"].split("-")[-1]))
        except (KeyError, TypeError, ValueError):
            continue
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def add_event(event_type: str, target_id: str, summary: str, payload: dict | None = None) -> None:
    events = store()["events"]
    events.insert(0, {"id":next_id("events", "EV"),"type":event_type,"target_id":target_id,"summary":summary,"occurred_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"actor":st.session_state.get("user",{}).get("email","admin"),"payload":payload or {}})


def update(collection: str, item_id: str, values: dict) -> dict:
    for item in store()[collection]:
        if item["id"] == item_id:
            item.update(values)
            return item
    raise KeyError(item_id)
