"""좌석 API 요청·응답 Schema."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.dy.flight_schema import CabinClass


class SeatStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"


class SeatRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    flight_id: UUID
    seat_number: str
    cabin_class: CabinClass
    price: int = Field(gt=0)
    status: SeatStatus


class SeatCreate(BaseModel):
    """관리자 좌석 생성 요청."""

    model_config = ConfigDict(extra="forbid")

    seat_number: str = Field(
        min_length=2,
        max_length=5,
        pattern=r"^[1-9][0-9]{0,2}[A-Z]$",
    )
    cabin_class: CabinClass
    price: int = Field(gt=0, le=100_000_000)
    status: SeatStatus = SeatStatus.AVAILABLE

    @model_validator(mode="after")
    def prevent_manual_booked_creation(self) -> "SeatCreate":
        if self.status is SeatStatus.BOOKED:
            raise ValueError("BOOKED 상태는 예약 생성 과정에서만 설정할 수 있습니다.")
        return self


class SeatUpdate(BaseModel):
    """관리자 좌석 부분 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    seat_number: str | None = Field(
        default=None,
        min_length=2,
        max_length=5,
        pattern=r"^[1-9][0-9]{0,2}[A-Z]$",
    )
    cabin_class: CabinClass | None = None
    price: int | None = Field(default=None, gt=0, le=100_000_000)
    status: SeatStatus | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> "SeatUpdate":
        if not self.model_fields_set:
            raise ValueError("수정할 필드를 하나 이상 입력해야 합니다.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("수정 필드에는 null을 입력할 수 없습니다.")
        if self.status is SeatStatus.BOOKED:
            raise ValueError("BOOKED 상태는 예약 생성 과정에서만 설정할 수 있습니다.")
        return self
