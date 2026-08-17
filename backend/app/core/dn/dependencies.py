from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dn.supabase_client import get_supabase_client
from app.exceptions.handlers import AppException

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise AppException(401, "UNAUTHORIZED", "로그인이 필요합니다.")

    token = credentials.credentials
    supabase = get_supabase_client()

    session_result = (
        supabase.table("sessions")
        .select("user_id, expires_at")
        .eq("token", token)
        .execute()
    )
    session = session_result.data[0] if session_result.data else None
    if session is None:
        raise AppException(401, "UNAUTHORIZED", "유효하지 않은 세션입니다.")

    expires_at = datetime.fromisoformat(session["expires_at"]).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise AppException(401, "SESSION_EXPIRED", "세션이 만료되었습니다. 다시 로그인해주세요.")

    user_result = (
        supabase.table("users")
        .select("id, email, name, role, profile_image_url")
        .eq("id", session["user_id"])
        .execute()
    )
    user = user_result.data[0] if user_result.data else None
    if user is None:
        raise AppException(401, "UNAUTHORIZED", "사용자를 찾을 수 없습니다.")

    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    """인증 헤더가 없으면 익명 사용자를 허용하고, 있으면 토큰을 검증합니다."""

    if credentials is None:
        return None

    return await get_current_user(credentials)


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "ADMIN":
        raise AppException(403, "FORBIDDEN", "관리자만 접근할 수 있습니다.")
    return current_user
