from app.core.dn.supabase_client import get_supabase_client
from app.exceptions.handlers import AppException
from app.schemas.dn.auth_schema import UserPublic
from app.schemas.dn.user_schema import (
    UserListResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)

USER_PUBLIC_COLUMNS = (
    "id, email, name, phone, role, profile_image_url, created_at"
)


def get_my_profile(user_id: str) -> UserPublic:
    supabase = get_supabase_client()

    result = (
        supabase.table("users")
        .select(USER_PUBLIC_COLUMNS)
        .eq("id", user_id)
        .execute()
    )
    user = result.data[0] if result.data else None

    if user is None:
        raise AppException(404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")

    return UserPublic(**user)


def update_my_profile(user_id: str, payload: UserUpdateRequest) -> UserPublic:
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise AppException(400, "NO_UPDATE_FIELDS", "수정할 항목을 입력해주세요.")

    supabase = get_supabase_client()
    result = (
        supabase.table("users")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )

    user = result.data[0] if result.data else None
    if user is None:
        raise AppException(404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")

    return UserPublic(**user)


def list_users(offset: int, limit: int) -> UserListResponse:
    supabase = get_supabase_client()

    result = (
        supabase.table("users")
        .select(USER_PUBLIC_COLUMNS, count="exact")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return UserListResponse(
        items=[UserPublic(**user) for user in result.data],
        total=result.count or 0,
        offset=offset,
        limit=limit,
    )


def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
) -> UserPublic:
    supabase = get_supabase_client()

    result = (
        supabase.table("users")
        .update({"role": payload.role})
        .eq("id", user_id)
        .execute()
    )

    user = result.data[0] if result.data else None
    if user is None:
        raise AppException(404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")

    return UserPublic(**user)