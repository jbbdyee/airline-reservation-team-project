"""기존 사용자 피드백 화면과 실제 API를 연결하는 클라이언트."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.api_client import BackendAPIError, request


MAX_COMMENT_LENGTH = 1000


def _submitted_feedbacks() -> list[dict]:
    """
    화면에서 제출 완료 상태를 유지하기 위한 세션 데이터입니다.

    실제 피드백 데이터는 Supabase에 저장됩니다.
    """

    return st.session_state.setdefault(
        "submitted_feedbacks",
        [],
    )


def _find_chat_message(
    message_id: Any,
) -> dict | None:
    messages = st.session_state.get(
        "chat_messages",
        [],
    )

    return next(
        (
            message
            for message in messages
            if str(message.get("message_id"))
            == str(message_id)
        ),
        None,
    )


def is_feedback_submitted(
    user_id: Any,
    message_id: Any,
) -> bool:
    # 백엔드는 토큰으로 사용자를 식별하므로
    # 기존 호출 호환용 user_id는 비교하지 않습니다.
    del user_id

    return any(
        str(feedback.get("message_id"))
        == str(message_id)
        for feedback in _submitted_feedbacks()
    )


def _validate(
    score: int,
    comment: str,
) -> str:
    if score < 1 or score > 5:
        raise BackendAPIError(
            "평점은 1점부터 5점까지 선택할 수 있습니다."
        )

    normalized_comment = comment.strip()

    if len(normalized_comment) > MAX_COMMENT_LENGTH:
        raise BackendAPIError(
            f"의견은 {MAX_COMMENT_LENGTH}자 이내로 입력해 주세요."
        )

    return normalized_comment


def create_feedback(
    user_id: Any,
    message_id: Any,
    score: int,
    comment: str,
) -> dict:
    """
    기존 함수 인자를 유지하면서 챗봇 평가를 등록합니다.
    """

    del user_id

    normalized_comment = _validate(
        score,
        comment,
    )

    if is_feedback_submitted(None, message_id):
        raise BackendAPIError(
            "이미 평가한 챗봇 답변입니다."
        )

    message = _find_chat_message(message_id)

    if not message:
        raise BackendAPIError(
            "평가할 챗봇 메시지를 찾을 수 없습니다."
        )

    conversation_id = message.get(
        "conversation_id"
    )

    assistant_message_id = message.get(
        "assistant_message_id"
    )

    if not conversation_id or not assistant_message_id:
        raise BackendAPIError(
            "이전 가짜 챗봇 답변은 평가할 수 없습니다. "
            "새 질문을 등록한 후 다시 시도해 주세요."
        )

    payload = request(
        "POST",
        "/chat/feedbacks",
        json={
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_message_id,
            "rating": score,
            "comment": normalized_comment or None,
        },
    )

    _submitted_feedbacks().append(
        {
            "message_id": message_id,
            "feedback_id": (
                payload.get("id")
                if isinstance(payload, dict)
                else None
            ),
        }
    )

    return payload


def create_service_feedback(
    user_id: Any,
    score: int,
    comment: str,
) -> dict:
    """
    기존 서비스 피드백 화면을 유지하면서 실제 API에 등록합니다.
    """

    # 사용자 ID는 백엔드가 세션 토큰으로 판단합니다.
    del user_id

    normalized_comment = _validate(
        score,
        comment,
    )

    return request(
        "POST",
        "/feedbacks",
        json={
            "rating": score,
            "category": "SERVICE",
            "comment": normalized_comment or None,
        },
    )