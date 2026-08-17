"""인증 의존성을 주입받는 사용자·관리자 예약 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.core.dy.principal import principal_user_id
from app.schemas.dy.booking_schema import (
    BookingCancel,
    BookingCreate,
    BookingPage,
    BookingRead,
    BookingStatus,
    BookingStatusUpdate,
)
from app.services.dy.booking_service import (
    BookingAccessDeniedError,
    BookingAlreadyCancelledError,
    BookingFlightNotFoundError,
    BookingNotCancellableError,
    BookingNotFoundError,
    BookingSeatNotFoundError,
    FlightNotBookableError,
    FlightSeatMismatchError,
    SeatAlreadyBookedError,
    cancel_booking,
    create_booking,
    get_booking,
    list_admin_bookings,
    list_my_bookings,
    update_booking_status,
)


def _booking_error(error: Exception) -> JSONResponse:
    mapping: tuple[tuple[type[Exception], int, str, str], ...] = (
        (BookingAccessDeniedError, 403, "BOOKING_ACCESS_DENIED", "예약에 접근할 권한이 없습니다."),
        (BookingNotFoundError, 404, "BOOKING_NOT_FOUND", "예약을 찾을 수 없습니다."),
        (BookingFlightNotFoundError, 404, "FLIGHT_NOT_FOUND", "항공편을 찾을 수 없습니다."),
        (BookingSeatNotFoundError, 404, "SEAT_NOT_FOUND", "좌석을 찾을 수 없습니다."),
        (SeatAlreadyBookedError, 409, "SEAT_ALREADY_BOOKED", "이미 예약된 좌석입니다."),
        (FlightSeatMismatchError, 409, "FLIGHT_SEAT_MISMATCH", "좌석이 선택한 항공편에 속하지 않습니다."),
        (FlightNotBookableError, 409, "FLIGHT_NOT_BOOKABLE", "현재 예약할 수 없는 항공편입니다."),
        (BookingAlreadyCancelledError, 409, "BOOKING_ALREADY_CANCELLED", "이미 취소된 예약입니다."),
        (BookingNotCancellableError, 409, "BOOKING_NOT_CANCELLABLE", "현재 취소할 수 없는 예약입니다."),
    )
    for exception_type, status_code, error_code, message in mapping:
        if isinstance(error, exception_type):
            return JSONResponse(
                status_code=status_code,
                content=error_response(message=message, error_code=error_code),
            )
    raise error


def build_booking_router(
    current_user_dependency: Callable[..., Any],
    admin_dependency: Callable[..., Any],
) -> APIRouter:
    """dn 인증 함수가 확정되면 두 의존성을 전달해 Router를 생성한다."""

    booking_router = APIRouter(tags=["Booking"])

    @booking_router.post(
        "/bookings",
        response_model=ApiResponse[BookingRead],
        status_code=status.HTTP_201_CREATED,
    )
    def create_booking_route(
        data: BookingCreate,
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[BookingRead] | JSONResponse:
        try:
            booking = create_booking(client, principal_user_id(principal), data)
        except Exception as error:
            return _booking_error(error)
        return ApiResponse(
            success=True,
            message="예약을 생성했습니다.",
            data=booking,
        )

    @booking_router.get("/bookings/me", response_model=ApiResponse[BookingPage])
    def list_my_bookings_route(
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
        booking_status: Annotated[
            BookingStatus | None, Query(alias="status")
        ] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> ApiResponse[BookingPage]:
        result = list_my_bookings(
            client,
            principal_user_id(principal),
            status=booking_status,
            page=page,
            page_size=page_size,
        )
        return ApiResponse(
            success=True,
            message="내 예약 목록을 조회했습니다.",
            data=result,
        )

    @booking_router.get(
        "/bookings/{booking_id}",
        response_model=ApiResponse[BookingRead],
    )
    def get_booking_route(
        booking_id: UUID,
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[BookingRead] | JSONResponse:
        try:
            booking = get_booking(
                client,
                booking_id,
                requester_user_id=principal_user_id(principal),
            )
        except Exception as error:
            return _booking_error(error)
        return ApiResponse(
            success=True,
            message="예약 상세를 조회했습니다.",
            data=booking,
        )

    @booking_router.put(
        "/bookings/{booking_id}/cancel",
        response_model=ApiResponse[BookingRead],
    )
    def cancel_booking_route(
        booking_id: UUID,
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
        data: Annotated[BookingCancel, Body()] = BookingCancel(),
    ) -> ApiResponse[BookingRead] | JSONResponse:
        try:
            booking = cancel_booking(
                client,
                booking_id,
                principal_user_id(principal),
                data,
            )
        except Exception as error:
            return _booking_error(error)
        return ApiResponse(
            success=True,
            message="예약을 취소했습니다.",
            data=booking,
        )

    @booking_router.get(
        "/admin/bookings",
        response_model=ApiResponse[BookingPage],
        tags=["admin"],
    )
    def list_admin_bookings_route(
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
        booking_status: Annotated[
            BookingStatus | None, Query(alias="status")
        ] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> ApiResponse[BookingPage]:
        result = list_admin_bookings(
            client,
            status=booking_status,
            page=page,
            page_size=page_size,
        )
        return ApiResponse(
            success=True,
            message="전체 예약 목록을 조회했습니다.",
            data=result,
        )

    @booking_router.put(
        "/admin/bookings/{booking_id}/status",
        response_model=ApiResponse[BookingRead],
        tags=["admin"],
    )
    def update_booking_status_route(
        booking_id: UUID,
        data: BookingStatusUpdate,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[BookingRead] | JSONResponse:
        try:
            booking = update_booking_status(
                client,
                booking_id,
                principal_user_id(principal),
                data,
            )
        except Exception as error:
            return _booking_error(error)
        return ApiResponse(
            success=True,
            message="예약 상태를 변경했습니다.",
            data=booking,
        )

    return booking_router
