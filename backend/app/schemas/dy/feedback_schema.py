"""일반 피드백과 챗봇 상담 평가 Schema."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FeedbackCategory(StrEnum):
    SERVICE = "SERVICE"
    SEARCH = "SEARCH"
    BOOKING = "BOOKING"
    CHATBOT = "CHATBOT"
    ETC = "ETC"


class ChatIssueType(StrEnum):
    INACCURATE = "INACCURATE"
    MISUNDERSTOOD = "MISUNDERSTOOD"
    INSUFFICIENT = "INSUFFICIENT"
    SLOW = "SLOW"
    ETC = "ETC"


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    category: FeedbackCategory
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def reject_chatbot_category(self) -> "FeedbackCreate":
        if self.category is FeedbackCategory.CHATBOT:
            raise ValueError("챗봇 평가는 전용 API를 사용해야 합니다.")
        return self


class ChatFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    assistant_message_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    user_id: UUID
    rating: int = Field(ge=1, le=5)
    category: FeedbackCategory
    comment: str | None = None
    conversation_id: UUID | None = None
    assistant_message_id: UUID | None = None
    issue_type: ChatIssueType | None = None
    improvement_note: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime

    @field_validator("reviewed_at", "created_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class FeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int | None = Field(default=None, ge=1, le=5)
    category: FeedbackCategory | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("기간에는 UTC offset이 포함되어야 합니다.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_period(self) -> "FeedbackFilter":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("종료 시각은 시작 시각보다 빠를 수 없습니다.")
        return self


class ChatFeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_rating: int = Field(default=2, ge=1, le=5)
    has_comment: bool | None = None
    conversation_id: UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return FeedbackFilter.require_timezone(value)

    @model_validator(mode="after")
    def validate_period(self) -> "ChatFeedbackFilter":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("종료 시각은 시작 시각보다 빠를 수 없습니다.")
        return self


class FeedbackPage(BaseModel):
    items: list[FeedbackRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ChatFeedbackSummary(BaseModel):
    average_rating: float | None
    rating_counts: dict[int, int]
    total_count: int = Field(ge=0)
    low_rating_count: int = Field(ge=0)
    low_rating_ratio: float = Field(ge=0, le=1)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    user_id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ChatFeedbackDetail(BaseModel):
    feedback: FeedbackRead
    selected_assistant_message: ChatMessageRead
    messages: list[ChatMessageRead]


class ChatFeedbackReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: ChatIssueType
    improvement_note: str = Field(min_length=1, max_length=2000)

    @field_validator("improvement_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("개선 메모는 공백만 입력할 수 없습니다.")
        return value
