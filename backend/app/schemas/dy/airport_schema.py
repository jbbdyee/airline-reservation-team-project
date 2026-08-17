"""공항 API 요청·응답 Schema."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AirportRead(BaseModel):
    """검색 화면에 제공하는 공항 정보."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    iata_code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    country: str = Field(min_length=1)

    @field_validator("name", "city", "country")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("공백만 입력할 수 없습니다.")
        return value
