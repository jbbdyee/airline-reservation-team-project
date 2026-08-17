"""기존 채팅 화면과 실제 챗봇 API를 연결하는 클라이언트."""

from __future__ import annotations

from core.api_client import BackendAPIError, request


MAX_QUESTION_LENGTH = 500


def send_message(
    question: str,
    conversation_id: str | None = None,
) -> dict:
    question = question.strip()

    if not question:
        raise BackendAPIError(
            "질문을 입력해 주세요."
        )

    if len(question) > MAX_QUESTION_LENGTH:
        raise BackendAPIError(
            f"질문은 {MAX_QUESTION_LENGTH}자 이내로 입력해 주세요."
        )

    request_body = {
        "message": question,
    }

    if conversation_id:
        request_body["conversation_id"] = conversation_id

    payload = request(
        "POST",
        "/chat/messages",
        json=request_body,
    )

    if not isinstance(payload, dict):
        raise BackendAPIError(
            "챗봇 응답 형식이 올바르지 않습니다."
        )

    assistant_message_id = payload.get(
        "assistant_message_id"
    )

    conversation_id = payload.get(
        "conversation_id"
    )

    if not assistant_message_id or not conversation_id:
        raise BackendAPIError(
            "챗봇 응답에 메시지 식별자가 없습니다."
        )

    # 기존 06_chat.py와 chat_widget.py가 기대하는
    # question/answer/message_id 필드를 그대로 제공합니다.
    return {
        "message_id": assistant_message_id,
        "question": question,
        "answer": payload.get("answer", ""),
        "created_at": payload.get("created_at"),

        # 피드백 등록에 필요한 실제 UUID
        "conversation_id": conversation_id,
        "user_message_id": payload.get(
            "user_message_id"
        ),
        "assistant_message_id": assistant_message_id,
    }
