from app.core.dy.api_response import APIResponse, error_response, success_response


def test_success_response_has_common_shape() -> None:
    result = success_response(data={"flight_id": "flight-1"}, message="조회 성공")

    assert result == {
        "success": True,
        "data": {"flight_id": "flight-1"},
        "message": "조회 성공",
        "error_code": None,
    }


def test_error_response_has_common_shape() -> None:
    result = error_response(
        message="항공편을 찾을 수 없습니다.",
        error_code="FLIGHT_NOT_FOUND",
    )

    assert result == {
        "success": False,
        "data": None,
        "message": "항공편을 찾을 수 없습니다.",
        "error_code": "FLIGHT_NOT_FOUND",
    }


def test_api_response_supports_typed_data() -> None:
    response = APIResponse[dict[str, int]](
        success=True,
        data={"total": 2},
        message="집계 성공",
    )

    assert response.data == {"total": 2}
