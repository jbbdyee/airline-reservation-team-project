"""공항 목록 API 요청 함수."""

from core.api_client import as_list, request


def get_airports(
    keyword: str = "",
) -> list[dict]:
    keyword = keyword.strip()

    params = (
        {"keyword": keyword}
        if keyword
        else None
    )

    return as_list(
        request(
            "GET",
            "/airports",
            params=params,
        )
    )