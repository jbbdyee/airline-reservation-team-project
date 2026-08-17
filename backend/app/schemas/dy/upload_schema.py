"""이미지 업로드 응답 Schema."""

from pydantic import BaseModel, Field


class ImageUploadRead(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int = Field(gt=0)
