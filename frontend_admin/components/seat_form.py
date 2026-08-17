"""좌석 관리 화면의 선택값입니다."""


SEAT_CLASS_OPTIONS = {
    "이코노미": "ECONOMY",
    "비즈니스": "BUSINESS",
}

SEAT_STATUS_OPTIONS = {
    "예약 가능": "AVAILABLE",
    "점검 중": "HELD",
}

SEAT_CLASS_LABELS = {
    value: label
    for label, value
    in SEAT_CLASS_OPTIONS.items()
}

SEAT_STATUS_LABELS = {
    "AVAILABLE": "예약 가능",
    "HELD": "점검 중",
    "BOOKED": "예약 완료",
}