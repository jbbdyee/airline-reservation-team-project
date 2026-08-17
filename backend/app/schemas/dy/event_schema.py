"""이벤트 로그 조회·SSE Schema."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(StrEnum):
    FLIGHT_STATUS_CHANGED = "FLIGHT_STATUS_CHANGED"
    SEAT_CHANGED = "SEAT_CHANGED"
    BOOKING_CHANGED = "BOOKING_CHANGED"


class EventLogRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    event_type: EventType
    resource_id: UUID
    flight_id: UUID | None = None
    booking_id: UUID | None = None
    actor_user_id: UUID | None = None
    payload: dict[str, Any]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class EventLogFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType | None = None
    flight_id: UUID | None = None
    booking_id: UUID | None = None
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
    def validate_period(self) -> "EventLogFilter":
        if self.start_at is not None and self.end_at is not None:
            if self.end_at < self.start_at:
                raise ValueError("종료 시각은 시작 시각보다 빠를 수 없습니다.")
        return self


class EventLogPage(BaseModel):
    items: list[EventLogRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
