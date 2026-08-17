from __future__ import annotations

import base64

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.routers.dy.upload_router import build_upload_router


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def current_user():
    return {"id": "00000000-0000-0000-0000-00000000b002", "role": "USER"}


def create_client(tmp_path, dependency=current_user) -> TestClient:
    app = FastAPI()
    app.include_router(build_upload_router(dependency, upload_dir=tmp_path))
    return TestClient(app)


def test_upload_route_accepts_real_png_and_returns_201(tmp_path) -> None:
    response = create_client(tmp_path).post(
        "/uploads/images",
        files={"file": ("../../profile.png", PNG_1X1, "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["content_type"] == "image/png"
    assert body["data"]["url"].startswith("/static/uploads/")
    stored = tmp_path / body["data"]["filename"]
    assert stored.read_bytes() == PNG_1X1


def test_upload_route_rejects_fake_png_with_common_error(tmp_path) -> None:
    response = create_client(tmp_path).post(
        "/uploads/images",
        files={"file": ("profile.png", b"not-an-image", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_IMAGE"
    assert list(tmp_path.iterdir()) == []


def test_upload_route_rejects_unsupported_type(tmp_path) -> None:
    response = create_client(tmp_path).post(
        "/uploads/images",
        files={"file": ("profile.svg", b"<svg></svg>", "image/svg+xml")},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "UNSUPPORTED_IMAGE_TYPE"


def test_upload_route_requires_login(tmp_path) -> None:
    def denied_user():
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    response = create_client(tmp_path, denied_user).post(
        "/uploads/images",
        files={"file": ("profile.png", PNG_1X1, "image/png")},
    )

    assert response.status_code == 401
    assert list(tmp_path.iterdir()) == []


def test_upload_route_requires_file_part(tmp_path) -> None:
    response = create_client(tmp_path).post("/uploads/images")

    assert response.status_code == 422
