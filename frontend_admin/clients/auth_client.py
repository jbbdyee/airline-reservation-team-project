"""관리자 인증 API 요청 함수."""

from core.api_client import request


def is_demo_mode() -> bool:
    return False

def signin(
    email: str,
    password: str,
) -> dict:
    return request(
        "POST",
        "/auth/signin",
        data={
            "email": email.strip().lower(),
            "password": password,
        },
    )


def signout() -> None:
    request(
        "POST",
        "/auth/signout",
    )