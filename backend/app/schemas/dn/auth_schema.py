from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=50)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    phone: str | None = None
    role: str
    profile_image_url: str | None = None
    created_at: datetime


class SigninResponse(BaseModel):
    user: UserPublic
    session_token: str
    expires_at: datetime