"""좌석 생성·조회·수정·삭제 API 요청 함수."""

from clients.auth_client import is_demo_mode
from core.api_client import BackendAPIError, as_list, request
from core.demo_store import add_event, next_id, store, update


def get_seats(flight_id: str, cabin_class: str | None = None) -> list[dict]:
    params = None

    if cabin_class:
        params = {
            "cabin_class": cabin_class,
        }

    payload = request(
        "GET",
        f"/flights/{flight_id}/seats",
        params=params,
    )

    return as_list(payload)

def create_seat(flight_id: str, seat: dict) -> dict:
    return request(
        "POST",
        f"/flights/{flight_id}/seats",
        json=seat,
    )


def update_seat(seat_id: str, seat: dict) -> dict:
    return request(
        "PUT",
        f"/seats/{seat_id}",
        json=seat,
    )



def delete_seat(seat_id: str) -> None:
    request(
        "DELETE",
        f"/seats/{seat_id}",
    )
