"""API 성공/실패 응답의 공통 형식을 정의한다."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """수업 예제와 동일한 이름을 사용하는 공통 응답 모델."""

    success: bool
    data: DataT | None = None
    message: str
    error_code: str | None = None


# 기존 코드와 API 문서의 타입 참조가 깨지지 않도록 호환 이름을 유지한다.
APIResponse = ApiResponse


def success_response(
    data: Any = None,
    message: str = "요청이 성공적으로 처리되었습니다.",
) -> dict[str, Any]:
    """성공 응답을 공통 형식의 직렬화 가능한 dict로 반환한다."""

    return ApiResponse[Any](
        success=True,
        data=data,
        message=message,
        error_code=None,
    ).model_dump()


def error_response(
    message: str,
    error_code: str,
    data: Any = None,
) -> dict[str, Any]:
    """실패 응답을 공통 형식의 직렬화 가능한 dict로 반환한다."""

    return ApiResponse[Any](
        success=False,
        data=data,
        message=message,
        error_code=error_code,
    ).model_dump()
