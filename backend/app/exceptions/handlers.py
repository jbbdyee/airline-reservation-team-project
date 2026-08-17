
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


class AppException(Exception):
    """서비스 계층에서 의도적으로 발생시키는 도메인 예외.

    status_code/error_code/message를 직접 지정해서 raise하면
    아래 핸들러가 공통 응답 형식으로 변환한다.
    예: raise AppException(409, "EMAIL_ALREADY_EXISTS", "이미 가입된 이메일입니다.")
    """

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "error_code": error_code,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return _error_response(exc.status_code, exc.error_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "요청 값이 올바르지 않습니다.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(
            exc.status_code,
            "HTTP_ERROR",
            str(exc.detail) if exc.detail else "요청을 처리할 수 없습니다.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "서버 오류가 발생했습니다.",
        )