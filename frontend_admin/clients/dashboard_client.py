"""관리자 대시보드 API 요청 함수."""

from core.api_client import request


def get_dashboard() -> dict:
    """관리자 대시보드 데이터를 조회합니다."""

    dashboard = request(
        "GET",
        "/admin/dashboard",
    )

    if not isinstance(dashboard, dict):
        return {}

    return dashboard