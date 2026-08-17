from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.dn.auth_schema import UserPublic


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    profile_image_url: str | None = Field(default=None, max_length=500)


class UserRoleUpdateRequest(BaseModel):
    role: Literal["USER", "ADMIN"]


class UserListResponse(BaseModel):
    items: list[UserPublic]
    total: int
    offset: int
    limit: int