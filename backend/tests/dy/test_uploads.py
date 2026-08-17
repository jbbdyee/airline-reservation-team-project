from __future__ import annotations

import asyncio
import base64
from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.dy.upload_service import (
    EmptyImageError,
    ImageTooLargeError,
    InvalidImageError,
    MAX_IMAGE_SIZE,
    UnsupportedImageTypeError,
    save_image,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def upload_file(data: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_save_image_uses_generated_name_and_static_url(tmp_path) -> None:
    upload = upload_file(PNG_1X1, "../../profile.php.png", "image/png")

    result = asyncio.run(save_image(upload, upload_dir=tmp_path))

    assert result.filename.endswith(".png")
    assert result.filename != upload.filename
    assert result.url == f"/static/uploads/{result.filename}"
    assert (tmp_path / result.filename).read_bytes() == PNG_1X1
    assert not list(tmp_path.glob("*.tmp"))


def test_save_image_rejects_unsupported_declared_type(tmp_path) -> None:
    upload = upload_file(PNG_1X1, "profile.svg", "image/svg+xml")

    with pytest.raises(UnsupportedImageTypeError):
        asyncio.run(save_image(upload, upload_dir=tmp_path))


def test_save_image_rejects_mime_signature_mismatch(tmp_path) -> None:
    upload = upload_file(PNG_1X1, "profile.jpg", "image/jpeg")

    with pytest.raises(InvalidImageError):
        asyncio.run(save_image(upload, upload_dir=tmp_path))


def test_save_image_rejects_fake_or_empty_image(tmp_path) -> None:
    fake = upload_file(b"<script>alert(1)</script>", "profile.png", "image/png")
    empty = upload_file(b"", "profile.png", "image/png")

    with pytest.raises(InvalidImageError):
        asyncio.run(save_image(fake, upload_dir=tmp_path))
    with pytest.raises(EmptyImageError):
        asyncio.run(save_image(empty, upload_dir=tmp_path))


def test_save_image_rejects_more_than_five_mebibytes(tmp_path) -> None:
    oversized = upload_file(
        b"\x89PNG\r\n\x1a\n" + b"IHDR" + b"0" * MAX_IMAGE_SIZE,
        "large.png",
        "image/png",
    )

    with pytest.raises(ImageTooLargeError):
        asyncio.run(save_image(oversized, upload_dir=tmp_path))
    assert list(tmp_path.iterdir()) == []
