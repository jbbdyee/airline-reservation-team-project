"""프로필 이미지 검증과 로컬 저장 로직."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from anyio import to_thread
from fastapi import UploadFile

from app.schemas.dy.upload_schema import ImageUploadRead


MAX_IMAGE_SIZE = 5 * 1024 * 1024
DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "static" / "uploads"
STATIC_URL_PREFIX = "/static/uploads"

IMAGE_FORMATS = {
    "jpeg": {"content_type": "image/jpeg", "extension": ".jpg"},
    "png": {"content_type": "image/png", "extension": ".png"},
    "gif": {"content_type": "image/gif", "extension": ".gif"},
    "webp": {"content_type": "image/webp", "extension": ".webp"},
}


class EmptyImageError(Exception):
    pass


class ImageTooLargeError(Exception):
    pass


class UnsupportedImageTypeError(Exception):
    pass


class InvalidImageError(Exception):
    pass


def _detect_image_format(
    data: bytes,
) -> str | None:
    """허용 형식의 핵심 파일 서명을 확인합니다."""

    if (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        and b"IHDR" in data[:33]
    ):
        return "png"

    if (
        len(data) >= 4
        and data.startswith(b"\xff\xd8\xff")
        and data.rfind(b"\xff\xd9") >= 0
    ):
        return "jpeg"

    if (
        data.startswith((b"GIF87a", b"GIF89a"))
        and b";" in data[-16:]
    ):
        return "gif"

    if (
        len(data) >= 16
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
        and int.from_bytes(
            data[4:8],
            "little",
        ) + 8 <= len(data)
    ):
        return "webp"

    return None


def _write_atomically(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


async def save_image(
    upload: UploadFile,
    upload_dir: Path = DEFAULT_UPLOAD_DIR,
    url_prefix: str = STATIC_URL_PREFIX,
) -> ImageUploadRead:
    """이미지를 검증한 뒤 서버가 만든 안전한 이름으로 저장한다."""

    declared_type = (upload.content_type or "").lower()
    allowed_types = {item["content_type"] for item in IMAGE_FORMATS.values()}
    if declared_type not in allowed_types:
        raise UnsupportedImageTypeError

    data = await upload.read(MAX_IMAGE_SIZE + 1)
    if not data:
        raise EmptyImageError
    if len(data) > MAX_IMAGE_SIZE:
        raise ImageTooLargeError

    detected_format = _detect_image_format(data)
    if detected_format is None:
        raise InvalidImageError
    format_info = IMAGE_FORMATS[detected_format]
    if declared_type != format_info["content_type"]:
        raise InvalidImageError

    filename = f"{uuid4().hex}{format_info['extension']}"
    target = upload_dir.resolve() / filename
    # filename은 서버가 생성하지만 저장 경계도 별도로 확인한다.
    if target.parent != upload_dir.resolve():
        raise InvalidImageError

    await to_thread.run_sync(_write_atomically, target, data)
    return ImageUploadRead(
        url=f"{url_prefix.rstrip('/')}/{filename}",
        filename=filename,
        content_type=format_info["content_type"],
        size=len(data),
    )
