"""인증 의존성을 주입받는 이벤트 로그·SSE Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from anyio import to_thread
from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.schemas.dy.event_schema import EventLogFilter, EventLogPage, EventLogRead
from app.services.dy.event_service import (
    EventLogNotFoundError,
    get_event_log,
    get_latest_event_id,
    list_event_logs,
    stream_event_logs,
)


def build_event_router(
    current_user_dependency: Callable[..., Any],
    admin_dependency: Callable[..., Any],
) -> APIRouter:
    event_router = APIRouter(tags=["Event"])

    @event_router.get(
        "/events/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "content": {"text/event-stream": {}},
                "description": "실시간 이벤트 스트림",
            }
        },
    )
    async def stream_events_route(
        request: Request,
        flight_id: Annotated[UUID | None, Query()] = None,
        last_event_id: Annotated[int | None, Query(ge=0)] = None,
        last_event_id_header: Annotated[
            int | None, Header(alias="Last-Event-ID", ge=0)
        ] = None,
        _principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
    ) -> StreamingResponse:
        cursor = last_event_id
        if cursor is None:
            cursor = last_event_id_header
        if cursor is None:
            cursor = await to_thread.run_sync(get_latest_event_id, client)

        return StreamingResponse(
            stream_event_logs(
                client,
                last_event_id=cursor,
                flight_id=flight_id,
                is_disconnected=request.is_disconnected,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @event_router.get(
        "/admin/event-logs",
        response_model=ApiResponse[EventLogPage],
        tags=["admin"],
    )
    def list_event_logs_route(
        filters: Annotated[EventLogFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[EventLogPage]:
        result = list_event_logs(client, filters)
        return ApiResponse(
            success=True,
            message="이벤트 로그 목록을 조회했습니다.",
            data=result,
        )

    @event_router.get(
        "/admin/event-logs/{event_log_id}",
        response_model=ApiResponse[EventLogRead],
        tags=["admin"],
    )
    def get_event_log_route(
        event_log_id: int,
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[EventLogRead] | JSONResponse:
        try:
            event = get_event_log(client, event_log_id)
        except EventLogNotFoundError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response(
                    message="이벤트 로그를 찾을 수 없습니다.",
                    error_code="EVENT_LOG_NOT_FOUND",
                ),
            )
        return ApiResponse(
            success=True,
            message="이벤트 로그 상세를 조회했습니다.",
            data=event,
        )

    return event_router
