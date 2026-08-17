"""인증 의존성을 주입받는 일반·챗봇 피드백 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.dn.supabase_client import get_supabase
from app.core.dy.api_response import ApiResponse, error_response
from app.core.dy.principal import principal_user_id
from app.schemas.dy.admin_schema import DashboardFilter
from app.schemas.dy.feedback_schema import (
    ChatFeedbackCreate,
    ChatFeedbackDetail,
    ChatFeedbackFilter,
    ChatFeedbackReview,
    ChatFeedbackSummary,
    FeedbackCreate,
    FeedbackFilter,
    FeedbackPage,
    FeedbackRead,
)
from app.services.dy.feedback_service import (
    AssistantMessageMismatchError,
    ChatConversationNotFoundError,
    ChatFeedbackAlreadyExistsError,
    FeedbackNotFoundError,
    create_chat_feedback,
    create_feedback,
    get_chat_feedback_detail,
    get_feedback,
    list_chat_feedbacks,
    list_feedbacks,
    review_chat_feedback,
    summarize_chat_feedbacks,
)


def _feedback_error(error: Exception) -> JSONResponse:
    mapping: tuple[tuple[type[Exception], int, str, str], ...] = (
        (
            ChatConversationNotFoundError,
            404,
            "CHAT_CONVERSATION_NOT_FOUND",
            "본인의 챗봇 상담을 찾을 수 없습니다.",
        ),
        (
            FeedbackNotFoundError,
            404,
            "FEEDBACK_NOT_FOUND",
            "피드백을 찾을 수 없습니다.",
        ),
        (
            ChatFeedbackAlreadyExistsError,
            409,
            "CHAT_FEEDBACK_ALREADY_EXISTS",
            "이미 평가한 상담입니다.",
        ),
        (
            AssistantMessageMismatchError,
            422,
            "ASSISTANT_MESSAGE_MISMATCH",
            "선택한 AI 답변이 해당 상담에 속하지 않습니다.",
        ),
    )
    for exception_type, status_code, error_code, message in mapping:
        if isinstance(error, exception_type):
            return JSONResponse(
                status_code=status_code,
                content=error_response(message=message, error_code=error_code),
            )
    raise error


def build_feedback_router(
    current_user_dependency: Callable[..., Any],
    admin_dependency: Callable[..., Any],
) -> APIRouter:
    feedback_router = APIRouter(tags=["Feedback"])

    @feedback_router.post(
        "/feedbacks",
        response_model=ApiResponse[FeedbackRead],
        status_code=status.HTTP_201_CREATED,
    )
    def create_feedback_route(
        data: FeedbackCreate,
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackRead]:
        feedback = create_feedback(client, principal_user_id(principal), data)
        return ApiResponse(
            success=True,
            message="피드백을 등록했습니다.",
            data=feedback,
        )

    @feedback_router.post(
        "/chat/feedbacks",
        response_model=ApiResponse[FeedbackRead],
        status_code=status.HTTP_201_CREATED,
    )
    def create_chat_feedback_route(
        data: ChatFeedbackCreate,
        principal: Any = Depends(current_user_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackRead] | JSONResponse:
        try:
            feedback = create_chat_feedback(
                client,
                principal_user_id(principal),
                data,
            )
        except Exception as error:
            return _feedback_error(error)
        return ApiResponse(
            success=True,
            message="챗봇 상담 평가를 등록했습니다.",
            data=feedback,
        )

    @feedback_router.get(
        "/admin/feedbacks",
        response_model=ApiResponse[FeedbackPage],
        tags=["admin"],
    )
    def list_feedbacks_route(
        filters: Annotated[FeedbackFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackPage]:
        result = list_feedbacks(client, filters)
        return ApiResponse(
            success=True,
            message="피드백 목록을 조회했습니다.",
            data=result,
        )

    @feedback_router.get(
        "/admin/feedbacks/{feedback_id}",
        response_model=ApiResponse[FeedbackRead],
        tags=["admin"],
    )
    def get_feedback_route(
        feedback_id: UUID,
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackRead] | JSONResponse:
        try:
            feedback = get_feedback(client, feedback_id)
        except Exception as error:
            return _feedback_error(error)
        return ApiResponse(
            success=True,
            message="피드백 상세를 조회했습니다.",
            data=feedback,
        )

    @feedback_router.get(
        "/admin/chat-feedbacks/summary",
        response_model=ApiResponse[ChatFeedbackSummary],
        tags=["admin"],
    )
    def summarize_chat_feedbacks_route(
        filters: Annotated[DashboardFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[ChatFeedbackSummary]:
        summary = summarize_chat_feedbacks(
            client,
            start_at=filters.start_at,
            end_at=filters.end_at,
        )
        return ApiResponse(
            success=True,
            message="챗봇 평가 현황을 조회했습니다.",
            data=summary,
        )

    @feedback_router.get(
        "/admin/chat-feedbacks",
        response_model=ApiResponse[FeedbackPage],
        tags=["admin"],
    )
    def list_chat_feedbacks_route(
        filters: Annotated[ChatFeedbackFilter, Query()],
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackPage]:
        result = list_chat_feedbacks(client, filters)
        return ApiResponse(
            success=True,
            message="챗봇 상담 평가 목록을 조회했습니다.",
            data=result,
        )

    @feedback_router.get(
        "/admin/chat-feedbacks/{feedback_id}",
        response_model=ApiResponse[ChatFeedbackDetail],
        tags=["admin"],
    )
    def get_chat_feedback_detail_route(
        feedback_id: UUID,
        _principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[ChatFeedbackDetail] | JSONResponse:
        try:
            detail = get_chat_feedback_detail(client, feedback_id)
        except Exception as error:
            return _feedback_error(error)
        return ApiResponse(
            success=True,
            message="챗봇 상담 평가 상세를 조회했습니다.",
            data=detail,
        )

    @feedback_router.put(
        "/admin/chat-feedbacks/{feedback_id}/review",
        response_model=ApiResponse[FeedbackRead],
        tags=["admin"],
    )
    def review_chat_feedback_route(
        feedback_id: UUID,
        data: ChatFeedbackReview,
        principal: Any = Depends(admin_dependency),
        client: Client = Depends(get_supabase),
    ) -> ApiResponse[FeedbackRead] | JSONResponse:
        try:
            feedback = review_chat_feedback(
                client,
                feedback_id,
                principal_user_id(principal),
                data,
            )
        except Exception as error:
            return _feedback_error(error)
        return ApiResponse(
            success=True,
            message="챗봇 평가 검토 결과를 저장했습니다.",
            data=feedback,
        )

    return feedback_router
