from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    answer: str
    created_at: datetime