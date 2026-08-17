"""기존 피드백 관리 화면과 백엔드 API를 연결하는 클라이언트."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from core.api_client import as_list, request


CATEGORY_LABELS = {
    "SERVICE": "서비스",
    "SEARCH": "항공편 검색",
    "BOOKING": "예약",
    "CHATBOT": "챗봇",
    "ETC": "기타",
}

ISSUE_LABELS = {
    "INACCURATE": "부정확",
    "MISUNDERSTOOD": "질문 이해 실패",
    "INSUFFICIENT": "정보 부족",
    "SLOW": "응답 지연",
    "ETC": "기타",
}

ISSUE_TO_API = {
    label: code
    for code, label in ISSUE_LABELS.items()
}


def _to_datetime(
    value: str | None,
    *,
    end_of_day: bool = False,
) -> str | None:
    if not value:
        return None

    try:
        parsed_date = date.fromisoformat(value)

        parsed_datetime = datetime.combine(
            parsed_date,
            time.max if end_of_day else time.min,
            tzinfo=ZoneInfo("Asia/Seoul"),
        )

        return parsed_datetime.isoformat()
    except ValueError:
        return value


def _normalize_feedback(
    feedback: dict[str, Any],
) -> dict[str, Any]:
    category = str(
        feedback.get("category", "")
    )

    issue_type = feedback.get("issue_type")

    return {
        "id": feedback.get("id", ""),
        "user_id": feedback.get("user_id", ""),
        "rating": int(feedback.get("rating", 0)),
        "category": CATEGORY_LABELS.get(
            category,
            category,
        ),
        "category_code": category,
        "comment": feedback.get("comment") or "",
        "content": feedback.get("comment") or "",
        "conversation_id": feedback.get(
            "conversation_id"
        ) or "",
        "assistant_message_id": feedback.get(
            "assistant_message_id"
        ) or "",
        "issue_type": ISSUE_LABELS.get(
            issue_type,
            issue_type or "",
        ),
        "issue_type_code": issue_type or "",
        "improvement_note": feedback.get(
            "improvement_note"
        ) or "",
        "reviewed_by": feedback.get(
            "reviewed_by"
        ) or "",
        "reviewed_at": feedback.get(
            "reviewed_at"
        ),
        "created_at": feedback.get(
            "created_at",
            "",
        ),
    }


def _prepare_params(
    params: dict | None,
) -> dict[str, Any]:
    source = dict(params or {})
    result: dict[str, Any] = {}

    for key in (
        "rating",
        "category",
        "max_rating",
        "has_comment",
        "conversation_id",
        "page",
        "page_size",
    ):
        value = source.get(key)

        if value is not None and value != "":
            result[key] = value

    result.setdefault("page", 1)
    result.setdefault("page_size", 100)

    start_at = _to_datetime(
        source.get("start_at")
    )
    end_at = _to_datetime(
        source.get("end_at"),
        end_of_day=True,
    )

    if start_at:
        result["start_at"] = start_at

    if end_at:
        result["end_at"] = end_at

    return result


def get_feedbacks(
    params: dict | None = None,
) -> list[dict]:
    payload = request(
        "GET",
        "/admin/feedbacks",
        params=_prepare_params(params),
    )

    return [
        _normalize_feedback(feedback)
        for feedback in as_list(payload)
        if isinstance(feedback, dict)
    ]


def get_feedback_detail(
    feedback_id: str,
) -> dict:
    payload = request(
        "GET",
        f"/admin/feedbacks/{feedback_id}",
    )

    if not isinstance(payload, dict):
        return {}

    return _normalize_feedback(payload)


def get_chat_feedback_summary(
    start_at: str | None = None,
    end_at: str | None = None,
) -> dict:
    params: dict[str, Any] = {}

    normalized_start = _to_datetime(start_at)
    normalized_end = _to_datetime(
        end_at,
        end_of_day=True,
    )

    if normalized_start:
        params["start_at"] = normalized_start

    if normalized_end:
        params["end_at"] = normalized_end

    payload = request(
        "GET",
        "/admin/chat-feedbacks/summary",
        params=params,
    )

    if not isinstance(payload, dict):
        return {
            "average_rating": 0,
            "rating_counts": {},
            "low_rating_ratio": 0,
        }

    # 기존 화면은 이미 퍼센트 값이라고 가정합니다.
    return {
        **payload,
        "average_rating": (
            payload.get("average_rating") or 0
        ),
        "low_rating_ratio": float(
            payload.get("low_rating_ratio", 0)
        ) * 100,
    }


def get_chat_feedbacks(
    params: dict | None = None,
) -> list[dict]:
    prepared = _prepare_params(params)

    # 기존 화면에서 평점을 선택하지 않으면 전체 조회
    if prepared.get("max_rating") is None:
        prepared["max_rating"] = 5

    payload = request(
        "GET",
        "/admin/chat-feedbacks",
        params=prepared,
    )

    return [
        _normalize_feedback(feedback)
        for feedback in as_list(payload)
        if isinstance(feedback, dict)
    ]


def get_chat_feedback_detail(
    feedback_id: str,
) -> dict:
    payload = request(
        "GET",
        f"/admin/chat-feedbacks/{feedback_id}",
    )

    if not isinstance(payload, dict):
        return {}

    raw_feedback = payload.get("feedback") or {}
    feedback = _normalize_feedback(raw_feedback)

    selected_message = (
        payload.get("selected_assistant_message")
        or {}
    )

    messages = payload.get("messages") or []

    user_messages = [
        message
        for message in messages
        if str(message.get("role", "")).upper()
        == "USER"
    ]

    question = (
        user_messages[-1].get("content", "")
        if user_messages
        else ""
    )

    answer = selected_message.get(
        "content",
        "",
    )

    # 기존 페이지가 기대하는 평면 구조로 반환
    return {
        **feedback,
        "question": question,
        "user_question": question,
        "answer": answer,
        "assistant_answer": answer,
        "messages": messages,
    }


def save_chat_feedback_review(
    feedback_id: str,
    issue_type: str,
    improvement_note: str,
) -> dict:
    backend_issue_type = ISSUE_TO_API.get(
        issue_type,
        issue_type.upper(),
    )

    payload = request(
        "PUT",
        f"/admin/chat-feedbacks/{feedback_id}/review",
        json={
            "issue_type": backend_issue_type,
            "improvement_note": improvement_note.strip(),
        },
    )

    if not isinstance(payload, dict):
        return {}

    return _normalize_feedback(payload)