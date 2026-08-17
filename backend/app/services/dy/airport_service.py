"""공항 조회 비즈니스 로직."""

from __future__ import annotations

from typing import Any

from supabase import Client

from app.schemas.dy.airport_schema import AirportRead


AIRPORT_COLUMNS = "id,iata_code,name,city,country"


def list_airports(client: Client, keyword: str | None = None) -> list[AirportRead]:
    """IATA 코드·공항명·도시명으로 공항을 조회한다.

    Router에서 PostgREST 필터 예약 문자를 허용하지 않으므로 `or_` 식에는
    검증된 검색어만 들어온다. 결과는 프론트엔드 선택 목록이 안정적으로
    표시되도록 IATA 코드 오름차순으로 정렬한다.
    """

    query = client.table("airports").select(AIRPORT_COLUMNS)
    normalized_keyword = keyword.strip() if keyword else None

    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.or_(
            ",".join(
                (
                    f"iata_code.ilike.{pattern}",
                    f"name.ilike.{pattern}",
                    f"city.ilike.{pattern}",
                )
            )
        )

    response = query.order("iata_code").execute()
    rows: list[dict[str, Any]] = response.data or []
    return [AirportRead.model_validate(row) for row in rows]
