"""사용자 프론트엔드 공통 API 요청 기능."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv


FRONTEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(FRONTEND_DIR / ".env")

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "https://airline-reservation-team-project.onrender.com",
).rstrip("/")
# BACKEND_URL = os.getenv(
#     "BACKEND_URL",
#     "http://127.0.0.1:8000",
# ).rstrip("/")


class BackendAPIError(Exception):
    """백엔드 API 호출 실패를 표시하는 예외."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code


def request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    headers: dict[str, str] = {}

    session_token = st.session_state.get(
        "session_token",
        "",
    )

    if session_token:
        headers["Authorization"] = (
            f"Bearer {session_token}"
        )

    try:
        response = httpx.request(
            method,
            f"{BACKEND_URL}{path}",
            headers=headers,
            json=json,
            data=data,
            params=params,
            timeout=30,
        )
    except httpx.TimeoutException as error:
        raise BackendAPIError(
            "백엔드 응답 시간이 초과되었습니다."
        ) from error
    except httpx.RequestError as error:
        raise BackendAPIError(
            "백엔드 서버에 연결할 수 없습니다."
        ) from error

    if response.status_code == 204:
        return None

    try:
        payload = response.json()
    except ValueError as error:
        raise BackendAPIError(
            "백엔드가 올바른 JSON을 반환하지 않았습니다."
        ) from error

    if response.is_error:
        if isinstance(payload, dict):
            message = payload.get(
                "message",
                payload.get(
                    "detail",
                    "요청에 실패했습니다.",
                ),
            )
        else:
            message = "요청에 실패했습니다."

        raise BackendAPIError(
            str(message),
            response.status_code,
        )

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]

    return payload