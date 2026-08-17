"""dn 인증 의존성과 dy Router 사이의 최소 사용자 계약."""

from __future__ import annotations

from typing import Any
from uuid import UUID


class InvalidPrincipalError(RuntimeError):
    pass


def principal_user_id(principal: Any) -> UUID:
    """dict/Pydantic/객체 형태의 인증 사용자에서 UUID를 얻는다.

    dn이 반환할 최종 사용자 타입이 정해지기 전까지 `id`와 `user_id` 두
    관례를 모두 받아 Router와 인증 구현의 결합을 최소화한다.
    """

    value = None
    if isinstance(principal, dict):
        value = principal.get("id") or principal.get("user_id")
    else:
        value = getattr(principal, "id", None) or getattr(
            principal, "user_id", None
        )
    if value is None:
        raise InvalidPrincipalError("인증 사용자에 id 또는 user_id가 없습니다.")
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise InvalidPrincipalError("인증 사용자 ID가 UUID 형식이 아닙니다.") from error
