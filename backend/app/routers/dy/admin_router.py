"""인증 의존성을 주입받는 관리자 대시보드·항공편·좌석 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.core.dy.principal import principal_user_id
from app.schemas.dy.admin_schema import AdminDashboardRead, DashboardFilter
from app.schemas.dy.flight_schema import (
    AdminFlightFilter,
    FlightCreate,
    FlightDetail,
    FlightPage,
    FlightUpdate,
)
from app.schemas.dy.seat_schema import SeatCreate, SeatRead, SeatUpdate
from app.services.dy.admin_service import get_admin_dashboard
from app.services.dy.flight_service import (
    FlightConflictError,
    FlightInUseError,
    FlightNotFoundError,
    InvalidFlightStateError,
    create_flight,
    delete_flight,
    list_admin_flights,
    update_flight,
)
from app.services.dy.seat_service import (
    SeatAlreadyExistsError,
    SeatFlightNotFoundError,
    SeatInUseError,
    SeatNotFoundError,
    create_seat,
    delete_seat,
    update_seat,
)


def _admin_resource_error(error: Exception) -> JSONResponse:
    mapping: tuple[tuple[type[Exception], int, str, str], ...] = (
        (FlightNotFoundError, 404, "FLIGHT_NOT_FOUND", "항공편을 찾을 수 없습니다."),
        (SeatFlightNotFoundError, 404, "FLIGHT_NOT_FOUND", "항공편을 찾을 수 없습니다."),
        (SeatNotFoundError, 404, "SEAT_NOT_FOUND", "좌석을 찾을 수 없습니다."),
        (FlightConflictError, 409, "FLIGHT_CONFLICT", "동일한 항공편 편성이 이미 존재합니다."),
        (FlightInUseError, 409, "FLIGHT_IN_USE", "좌석 또는 예약이 연결된 항공편입니다."),
        (SeatAlreadyExistsError, 409, "SEAT_ALREADY_EXISTS", "같은 좌석 번호가 이미 존재합니다."),
        (SeatInUseError, 409, "SEAT_IN_USE", "예약과 연결된 좌석은 변경하거나 삭제할 수 없습니다."),
        (InvalidFlightStateError, 422, "INVALID_FLIGHT_STATE", str(error)),
    )
    for exception_type, status_code, error_code, message in mapping:
        if isinstance(error, exception_type):
            return JSONResponse(
                status_code=status_code,
                content=error_response(message=message, error_code=error_code),
            )
    raise error


def build_admin_router(admin_dependency: Callable[..., Any]) -> APIRouter:
    admin_router = APIRouter(tags=["Admin"])

    @admin_router.get(
        "/admin/dashboard",
        response_model=ApiResponse[AdminDashboardRead],
    )
    def get_admin_dashboard_route(
        filters: Annotated[DashboardFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[AdminDashboardRead]:
        dashboard = get_admin_dashboard(client, filters)
        return ApiResponse(
            success=True,
            message="관리자 대시보드를 조회했습니다.",
            data=dashboard,
        )

    @admin_router.get(
        "/admin/flights",
        response_model=ApiResponse[FlightPage],
    )
    def list_admin_flights_route(
        filters: Annotated[AdminFlightFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FlightPage]:
        result = list_admin_flights(client, filters)
        return ApiResponse(
            success=True,
            message="관리자 항공편 목록을 조회했습니다.",
            data=result,
        )

    @admin_router.post(
        "/flights",
        response_model=ApiResponse[FlightDetail],
        status_code=status.HTTP_201_CREATED,
    )
    def create_flight_route(
        data: FlightCreate,
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FlightDetail] | JSONResponse:
        try:
            flight = create_flight(client, data)
        except Exception as error:
            return _admin_resource_error(error)
        return ApiResponse(
            success=True,
            message="항공편을 생성했습니다.",
            data=flight,
        )

    @admin_router.put(
        "/flights/{flight_id}",
        response_model=ApiResponse[FlightDetail],
    )
    def update_flight_route(
        flight_id: UUID,
        data: FlightUpdate,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FlightDetail] | JSONResponse:
        try:
            flight = update_flight(
                client,
                flight_id,
                data,
                actor_user_id=principal_user_id(principal),
            )
        except Exception as error:
            return _admin_resource_error(error)
        return ApiResponse(
            success=True,
            message="항공편을 수정했습니다.",
            data=flight,
        )

    @admin_router.delete(
        "/flights/{flight_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
    )
    def delete_flight_route(
        flight_id: UUID,
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> Response | JSONResponse:
        try:
            delete_flight(client, flight_id)
        except Exception as error:
            return _admin_resource_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @admin_router.post(
        "/flights/{flight_id}/seats",
        response_model=ApiResponse[SeatRead],
        status_code=status.HTTP_201_CREATED,
    )
    def create_seat_route(
        flight_id: UUID,
        data: SeatCreate,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[SeatRead] | JSONResponse:
        try:
            seat = create_seat(
                client,
                flight_id,
                data,
                actor_user_id=principal_user_id(principal),
            )
        except Exception as error:
            return _admin_resource_error(error)
        return ApiResponse(
            success=True,
            message="좌석을 생성했습니다.",
            data=seat,
        )

    @admin_router.put(
        "/seats/{seat_id}",
        response_model=ApiResponse[SeatRead],
    )
    def update_seat_route(
        seat_id: UUID,
        data: SeatUpdate,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[SeatRead] | JSONResponse:
        try:
            seat = update_seat(
                client,
                seat_id,
                data,
                actor_user_id=principal_user_id(principal),
            )
        except Exception as error:
            return _admin_resource_error(error)
        return ApiResponse(
            success=True,
            message="좌석을 수정했습니다.",
            data=seat,
        )

    @admin_router.delete(
        "/seats/{seat_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
    )
    def delete_seat_route(
        seat_id: UUID,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> Response | JSONResponse:
        try:
            delete_seat(
                client,
                seat_id,
                actor_user_id=principal_user_id(principal),
            )
        except Exception as error:
            return _admin_resource_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return admin_router
