from datetime import datetime, timezone
from uuid import UUID, uuid4

from google import genai

from app.core.dn.config import settings
from app.core.dn.supabase_client import get_supabase_client
from app.exceptions.handlers import AppException
from app.schemas.dn.chat_schema import ChatMessageRequest, ChatMessageResponse

SYSTEM_PROMPT = """
당신은 항공권 예약 서비스의 AI 여행 도우미입니다.
항공편 검색, 예약, 취소, 좌석 선택 등 서비스 이용 방법을 친절하게 안내하세요.
실제 항공편 가격·좌석·예약 상태를 임의로 확정해서 말하지 말고,
정확한 정보가 필요하면 서비스의 검색 또는 예약 화면 이용을 안내하세요.
답변은 한국어로 간결하게 작성하세요.
""".strip()


def _request_gemini_answer(message: str) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"{SYSTEM_PROMPT}\n\n사용자 질문: {message}",
        )
    except Exception as exc:
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)

        if status_code == 429:
            raise AppException(
                429,
                "GEMINI_RATE_LIMITED",
                "AI 요청이 많습니다. 잠시 후 다시 시도해주세요.",
            ) from exc

        raise AppException(
            502,
            "GEMINI_API_ERROR",
            "AI 응답을 가져오지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc

    answer = getattr(response, "text", None)
    if not answer:
        raise AppException(
            502,
            "GEMINI_EMPTY_RESPONSE",
            "AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
        )

    return answer.strip()


def send_message(
    user_id: str | None,
    payload: ChatMessageRequest,
) -> ChatMessageResponse:
    supabase = get_supabase_client()

    conversation_id = payload.conversation_id or uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    created_at = datetime.now(timezone.utc)

    # 사용자 질문을 먼저 DB에 저장
    if user_id is not None:
        supabase.table("chat_messages").insert(
            {
                "id": str(user_message_id),
                "user_id": user_id,
                "conversation_id": str(conversation_id),
                "role": "USER",
                "content": payload.message,
                "created_at": created_at.isoformat(),
            }
        ).execute()

    answer = _request_gemini_answer(payload.message)

    # Gemini 답변도 같은 대화 ID로 저장
    if user_id is not None:
        supabase.table("chat_messages").insert(
            {
                "id": str(assistant_message_id),
                "user_id": user_id,
                "conversation_id": str(conversation_id),
                "role": "ASSISTANT",
                "content": answer,
                "created_at": created_at.isoformat(),
            }
        ).execute()

    return ChatMessageResponse(
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        answer=answer,
        created_at=created_at,
    )
