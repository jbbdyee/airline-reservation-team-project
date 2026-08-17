"""인증 의존성을 주입받는 이미지 업로드 Router."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.dy.api_response import ApiResponse, error_response
from app.schemas.dy.upload_schema import ImageUploadRead
from app.services.dy.upload_service import (
    DEFAULT_UPLOAD_DIR,
    EmptyImageError,
    ImageTooLargeError,
    InvalidImageError,
    UnsupportedImageTypeError,
    save_image,
)


def _upload_error(error: Exception) -> JSONResponse:
    mapping: tuple[tuple[type[Exception], str, str], ...] = (
        (
            UnsupportedImageTypeError,
            "UNSUPPORTED_IMAGE_TYPE",
            "지원하지 않는 이미지 형식입니다.",
        ),
        (ImageTooLargeError, "IMAGE_TOO_LARGE", "이미지는 5MiB 이하여야 합니다."),
        (EmptyImageError, "INVALID_IMAGE", "빈 이미지 파일은 업로드할 수 없습니다."),
        (InvalidImageError, "INVALID_IMAGE", "유효한 이미지 파일이 아닙니다."),
    )
    for exception_type, error_code, message in mapping:
        if isinstance(error, exception_type):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response(message=message, error_code=error_code),
            )
    raise error


def build_upload_router(
    current_user_dependency: Callable[..., Any],
    *,
    upload_dir: Path = DEFAULT_UPLOAD_DIR,
) -> APIRouter:
    upload_router = APIRouter(tags=["Upload"])

    @upload_router.post(
        "/uploads/images",
        response_model=ApiResponse[ImageUploadRead],
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_image_route(
        file: UploadFile = File(...),
        _principal: Any = Depends(current_user_dependency),
    ) -> ApiResponse[ImageUploadRead] | JSONResponse:
        try:
            result = await save_image(file, upload_dir=upload_dir)
        except Exception as error:
            return _upload_error(error)
        finally:
            await file.close()
        return ApiResponse(
            success=True,
            message="이미지를 업로드했습니다.",
            data=result,
        )

    return upload_router
