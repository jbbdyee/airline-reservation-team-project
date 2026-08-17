"""공항 조회 API Router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse
from app.schemas.dy.airport_schema import AirportRead
from app.services.dy.airport_service import list_airports


airport_router = APIRouter(prefix="/airports", tags=["Airport"])
# 기존 테스트와 통합 코드에서 사용하던 이름을 유지한다.
router = airport_router

AirportKeyword = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=50,
        pattern=r"^[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\s-]+$",
        description="IATA 코드, 공항명 또는 도시명",
    ),
]


@airport_router.get("", response_model=ApiResponse[list[AirportRead]])
def list_airports_route(
    client: Annotated[Client, Depends(get_supabase)],
    keyword: AirportKeyword = None,
) -> ApiResponse[list[AirportRead]]:
    """공항 전체 목록 또는 검색어와 일치하는 목록을 반환한다."""

    if keyword is not None and not keyword.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="검색어는 공백만 입력할 수 없습니다.",
        )

    airports = list_airports(client=client, keyword=keyword)
    return ApiResponse(
        success=True,
        message="공항 목록을 조회했습니다.",
        data=airports,
    )
