"""dy 담당 Router 전체를 조립하는 팩토리."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.routers.dy import airport_router, flight_router, seat_router
from app.routers.dy.admin_router import build_admin_router
from app.routers.dy.booking_router import build_booking_router
from app.routers.dy.event_router import build_event_router
from app.routers.dy.feedback_router import build_feedback_router
from app.routers.dy.upload_router import build_upload_router
from app.services.dy.upload_service import DEFAULT_UPLOAD_DIR


def build_dy_router(
    current_user_dependency: Callable[..., Any],
    admin_dependency: Callable[..., Any],
    *,
    upload_dir: Path = DEFAULT_UPLOAD_DIR,
) -> APIRouter:
    """공개 조회와 인증 기반 dy API를 하나의 Router로 반환한다."""

    router = APIRouter()
    router.include_router(airport_router.airport_router)
    router.include_router(flight_router.flight_router)
    router.include_router(seat_router.seat_router)
    router.include_router(
        build_booking_router(current_user_dependency, admin_dependency)
    )
    router.include_router(
        build_feedback_router(current_user_dependency, admin_dependency)
    )
    router.include_router(
        build_event_router(current_user_dependency, admin_dependency)
    )
    router.include_router(
        build_upload_router(current_user_dependency, upload_dir=upload_dir)
    )
    router.include_router(build_admin_router(admin_dependency))
    return router
