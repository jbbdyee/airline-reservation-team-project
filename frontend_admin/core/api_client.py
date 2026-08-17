"""모든 관리자 메뉴에서 공통으로 사용하는 HTTP 요청 기능."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st


BACKEND_URL = os.getenv(
    "BACKEND_URL",
    os.getenv(
        "BACKEND_BASE_URL",
        "https://airline-reservation-team-project.onrender.com",
    ),
).rstrip("/")
# BACKEND_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 60.0


class BackendAPIError(Exception):
    """백엔드 연결 또는 API 응답 처리 중 발생한 오류입니다."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
):
    """백엔드에 요청하고 공통 응답의 data 또는 JSON 본문을 반환합니다."""

    headers: dict[str, str] = {}
    access_token = st.session_state.get("access_token", "")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    try:
        response = httpx.request(
            method,
            f"{BACKEND_URL}{path}",
            headers=headers,
            json=json,
            data=data,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TimeoutException as error:
        raise BackendAPIError("백엔드 응답 시간이 초과되었습니다.") from error
    except httpx.RequestError as error:
        raise BackendAPIError(
            "백엔드 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요."
        ) from error

    if response.status_code == 204:
        return None

    try:
        payload = response.json()
    except ValueError as error:
        if response.is_error:
            raise BackendAPIError(
                f"백엔드 요청에 실패했습니다 ({response.status_code}).",
                response.status_code,
            ) from error
        raise BackendAPIError("백엔드가 올바른 JSON을 반환하지 않았습니다.") from error

    if response.is_error:
        detail = payload.get("detail", payload.get("message", "알 수 없는 오류")) if isinstance(payload, dict) else payload
        messages = {
            401: "로그인이 필요하거나 인증 정보가 올바르지 않습니다.",
            403: "관리자 권한이 필요합니다.",
            404: "요청한 정보를 찾을 수 없습니다.",
            409: "현재 상태에서는 요청을 처리할 수 없습니다.",
            422: "입력값을 확인해 주세요.",
        }
        message = messages.get(response.status_code, f"요청에 실패했습니다 ({response.status_code}).")
        raise BackendAPIError(f"{message} {detail}", response.status_code)

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def as_list(payload: Any) -> list[dict]:
    """목록 API의 list/items/results 형식을 화면용 리스트로 통일합니다."""

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "feedbacks", "event_logs", "bookings", "users", "flights", "seats"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []
