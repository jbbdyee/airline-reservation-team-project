"""관리자 대시보드 요청·응답 Schema."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.dy.event_schema import EventLogRead
from app.schemas.dy.feedback_schema import ChatFeedbackSummary


class DashboardFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("기간에는 UTC offset이 포함되어야 합니다.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_period(self) -> "DashboardFilter":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("종료 시각은 시작 시각보다 빠를 수 없습니다.")
        return self


class FlightMetrics(BaseModel):
    total: int = Field(ge=0)
    scheduled: int = Field(ge=0)
    delayed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    departed: int = Field(ge=0)


class BookingMetrics(BaseModel):
    total: int = Field(ge=0)
    confirmed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    confirmed_revenue: int = Field(ge=0)


class AdminDashboardRead(BaseModel):
    flights: FlightMetrics
    bookings: BookingMetrics
    chat_feedbacks: ChatFeedbackSummary
    recent_events: list[EventLogRead]
