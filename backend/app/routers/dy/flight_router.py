"""사용자 항공편 검색·상세 API Router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.schemas.dy.flight_schema import (
    FlightDetail,
    FlightSearchParams,
    FlightSummary,
)
from app.services.dy.flight_service import (
    FlightNotFoundError,
    get_flight,
    search_flights,
)


flight_router = APIRouter(prefix="/flights", tags=["Flight"])
# 기존 테스트와 통합 코드에서 사용하던 이름을 유지한다.
router = flight_router


@flight_router.get("", response_model=ApiResponse[list[FlightSummary]])
def search_flights_route(
    client: Annotated[Client, Depends(get_supabase)],
    params: Annotated[FlightSearchParams, Query()],
) -> ApiResponse[list[FlightSummary]]:
    """출발지·도착지·한국 출발일·좌석 조건으로 항공편을 검색한다."""

    flights = search_flights(client, params)
    return ApiResponse(
        success=True,
        message="항공편 검색을 완료했습니다.",
        data=flights,
    )


@flight_router.get("/{flight_id}", response_model=ApiResponse[FlightDetail])
def get_flight_route(
    flight_id: UUID,
    client: Annotated[Client, Depends(get_supabase)],
) -> ApiResponse[FlightDetail] | JSONResponse:
    """항공편 상세와 등급별 잔여 좌석을 조회한다."""

    try:
        flight = get_flight(client, flight_id)
    except FlightNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(
                message="요청한 항공편을 찾을 수 없습니다.",
                error_code="FLIGHT_NOT_FOUND",
            ),
        )

    return ApiResponse(
        success=True,
        message="항공편 상세를 조회했습니다.",
        data=flight,
    )
