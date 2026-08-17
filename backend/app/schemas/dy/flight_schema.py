"""항공편 API 요청·응답 Schema."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FlightStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    DEPARTED = "DEPARTED"


class CabinClass(StrEnum):
    ECONOMY = "ECONOMY"
    BUSINESS = "BUSINESS"


class FlightSortField(StrEnum):
    PRICE = "price"
    DEPARTURE_AT = "departure_at"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class FlightSearchParams(BaseModel):
    """사용자 항공편 검색 조건."""

    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    destination: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    date: date
    passengers: int = Field(ge=1, le=9)
    cabin_class: CabinClass
    sort_by: FlightSortField = FlightSortField.PRICE
    sort_order: SortOrder = SortOrder.ASC

    @field_validator("destination")
    @classmethod
    def destination_must_differ_from_origin(cls, value: str, info) -> str:
        if value == info.data.get("origin"):
            raise ValueError("출발지와 도착지는 달라야 합니다.")
        return value


class AirportBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    iata_code: str
    name: str
    city: str
    country: str


class FlightSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    flight_number: str
    origin: AirportBrief
    destination: AirportBrief
    departure_at: datetime
    arrival_at: datetime
    status: FlightStatus
    base_price: int = Field(gt=0)
    lowest_seat_price: int = Field(gt=0)
    available_seats: int = Field(ge=0)

    @field_validator("departure_at", "arrival_at")
    @classmethod
    def normalize_db_timestamp_to_utc(cls, value: datetime) -> datetime:
        # DB는 timestamp 컬럼을 UTC 규칙으로 저장하므로 timezone 정보가 없으면
        # UTC로 해석한다.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SeatAvailability(BaseModel):
    available_seats: int = Field(ge=0)
    lowest_price: int | None = Field(default=None, gt=0)


class FlightDetail(FlightSummary):
    seats_by_cabin_class: dict[CabinClass, SeatAvailability]


class AdminFlightFilter(BaseModel):
    """관리자 항공편 목록의 선택 검색 조건."""

    model_config = ConfigDict(extra="forbid")

    flight_number: str | None = Field(default=None, min_length=1, max_length=10)
    status: FlightStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("flight_number")
    @classmethod
    def normalize_flight_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("편명은 공백만 입력할 수 없습니다.")
        return value


class FlightPage(BaseModel):
    items: list[FlightDetail]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class FlightCreate(BaseModel):
    """관리자 항공편 생성 요청."""

    model_config = ConfigDict(extra="forbid")

    flight_number: str = Field(
        min_length=3,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
    )
    origin_airport_id: UUID
    destination_airport_id: UUID
    departure_at: datetime
    arrival_at: datetime
    status: FlightStatus = FlightStatus.SCHEDULED
    base_price: int = Field(gt=0, le=100_000_000)

    @field_validator("departure_at", "arrival_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("시간에는 UTC offset이 포함되어야 합니다.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_route_and_times(self) -> "FlightCreate":
        if self.origin_airport_id == self.destination_airport_id:
            raise ValueError("출발 공항과 도착 공항은 달라야 합니다.")
        if self.arrival_at <= self.departure_at:
            raise ValueError("도착 시각은 출발 시각보다 늦어야 합니다.")
        return self


class FlightUpdate(BaseModel):
    """관리자 항공편 부분 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    flight_number: str | None = Field(
        default=None,
        min_length=3,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
    )
    origin_airport_id: UUID | None = None
    destination_airport_id: UUID | None = None
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    status: FlightStatus | None = None
    base_price: int | None = Field(default=None, gt=0, le=100_000_000)

    @field_validator("departure_at", "arrival_at")
    @classmethod
    def require_timezone_when_present(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("시간에는 UTC offset이 포함되어야 합니다.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "FlightUpdate":
        if not self.model_fields_set:
            raise ValueError("수정할 필드를 하나 이상 입력해야 합니다.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("수정 필드에는 null을 입력할 수 없습니다.")
        if (
            self.origin_airport_id is not None
            and self.destination_airport_id is not None
            and self.origin_airport_id == self.destination_airport_id
        ):
            raise ValueError("출발 공항과 도착 공항은 달라야 합니다.")
        if (
            self.departure_at is not None
            and self.arrival_at is not None
            and self.arrival_at <= self.departure_at
        ):
            raise ValueError("도착 시각은 출발 시각보다 늦어야 합니다.")
        return self
