"""사용자 좌석 조회 API Router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.schemas.dy.flight_schema import CabinClass
from app.schemas.dy.seat_schema import SeatRead
from app.services.dy.seat_service import SeatFlightNotFoundError, list_seats


seat_router = APIRouter(tags=["Seat"])
# 기존 테스트와 통합 코드에서 사용하던 이름을 유지한다.
router = seat_router


@seat_router.get(
    "/flights/{flight_id}/seats",
    response_model=ApiResponse[list[SeatRead]],
)
def list_seats_route(
    flight_id: UUID,
    client: Annotated[Client, Depends(get_supabase)],
    cabin_class: Annotated[CabinClass | None, Query()] = None,
) -> ApiResponse[list[SeatRead]] | JSONResponse:
    """항공편 좌석 목록을 선택한 좌석 등급으로 조회한다."""

    try:
        seats = list_seats(client, flight_id, cabin_class)
    except SeatFlightNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(
                message="요청한 항공편을 찾을 수 없습니다.",
                error_code="FLIGHT_NOT_FOUND",
            ),
        )
    return ApiResponse(
        success=True,
        message="좌석 목록을 조회했습니다.",
        data=seats,
    )
