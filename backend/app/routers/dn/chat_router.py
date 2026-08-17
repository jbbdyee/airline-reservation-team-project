from fastapi import APIRouter, Depends

from app.core.dn.dependencies import get_optional_current_user
from app.schemas.dn.chat_schema import ChatMessageRequest, ChatMessageResponse
from app.services.dn import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatMessageResponse)
async def send_chat_message_route(
    payload: ChatMessageRequest,
    current_user: dict | None = Depends(get_optional_current_user),
) -> ChatMessageResponse:
    return chat_service.send_message(
        user_id=current_user["id"] if current_user else None,
        payload=payload,
    )
