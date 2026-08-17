from fastapi import APIRouter, Depends, Query

from app.core.dn.dependencies import get_current_user, require_admin
from app.schemas.dn.auth_schema import UserPublic
from app.schemas.dn.user_schema import (
    UserListResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from app.services.dn import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_my_profile_route(
    current_user: dict = Depends(get_current_user),
) -> UserPublic:
    return user_service.get_my_profile(current_user["id"])


@router.patch("/me", response_model=UserPublic)
async def update_my_profile_route(
    payload: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> UserPublic:
    return user_service.update_my_profile(current_user["id"], payload)


@router.get("", response_model=UserListResponse)
async def list_users_route(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_admin: dict = Depends(require_admin),
) -> UserListResponse:
    return user_service.list_users(offset, limit)


@router.patch("/{user_id}/role", response_model=UserPublic)
async def update_user_role_route(
    user_id: str,
    payload: UserRoleUpdateRequest,
    current_admin: dict = Depends(require_admin),
) -> UserPublic:
    return user_service.update_user_role(user_id, payload)