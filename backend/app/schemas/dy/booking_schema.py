"""예약 API 요청·응답 Schema."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.dy.flight_schema import AirportBrief, FlightStatus
from app.schemas.dy.seat_schema import SeatRead


class BookingStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flight_id: UUID
    seat_id: UUID
    passenger_name: str = Field(min_length=1, max_length=100)

    @field_validator("passenger_name")
    @classmethod
    def normalize_passenger_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("탑승객명은 공백만 입력할 수 없습니다.")
        return value


class BookingCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BookingStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BookingStatus


class BookingFlightRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    flight_number: str
    origin: AirportBrief
    destination: AirportBrief
    departure_at: datetime
    arrival_at: datetime
    status: FlightStatus

    @field_validator("departure_at", "arrival_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class BookingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    booking_code: str
    user_id: UUID
    flight: BookingFlightRead
    seat: SeatRead
    passenger_name: str
    status: BookingStatus
    total_price: int = Field(gt=0)
    created_at: datetime
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None

    @field_validator("created_at", "cancelled_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class BookingPage(BaseModel):
    items: list[BookingRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
