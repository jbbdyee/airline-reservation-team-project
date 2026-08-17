"""일반 피드백과 챗봇 상담 평가 비즈니스 로직."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

from app.schemas.dy.feedback_schema import (
    ChatFeedbackCreate,
    ChatFeedbackDetail,
    ChatFeedbackFilter,
    ChatFeedbackReview,
    ChatFeedbackSummary,
    ChatMessageRead,
    FeedbackCategory,
    FeedbackCreate,
    FeedbackFilter,
    FeedbackPage,
    FeedbackRead,
)


FEEDBACK_COLUMNS = (
    "id,user_id,rating,category,comment,conversation_id,assistant_message_id,"
    "issue_type,improvement_note,reviewed_by,reviewed_at,created_at"
)
CHAT_MESSAGE_COLUMNS = "id,user_id,conversation_id,role,content,created_at"


class FeedbackNotFoundError(Exception):
    pass


class ChatConversationNotFoundError(Exception):
    pass


class AssistantMessageMismatchError(Exception):
    pass


class ChatFeedbackAlreadyExistsError(Exception):
    pass


def _serialize_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def create_feedback(
    client: Client,
    user_id: UUID,
    data: FeedbackCreate,
) -> FeedbackRead:
    payload = data.model_dump(mode="json")
    payload["user_id"] = str(user_id)
    response = client.table("feedbacks").insert(payload).execute()
    rows = response.data or []
    if not rows:
        raise RuntimeError("피드백 생성 결과가 없습니다.")
    return FeedbackRead.model_validate(rows[0])


def _conversation_messages(
    client: Client,
    user_id: UUID,
    conversation_id: UUID,
) -> list[ChatMessageRead]:
    response = (
        client.table("chat_messages")
        .select(CHAT_MESSAGE_COLUMNS)
        .eq("user_id", str(user_id))
        .eq("conversation_id", str(conversation_id))
        .order("created_at")
        .execute()
    )
    return [ChatMessageRead.model_validate(row) for row in response.data or []]


def create_chat_feedback(
    client: Client,
    user_id: UUID,
    data: ChatFeedbackCreate,
) -> FeedbackRead:
    """본인 상담의 AI 답변에 상담당 한 번만 평가를 등록한다."""

    messages = _conversation_messages(client, user_id, data.conversation_id)
    if not messages:
        raise ChatConversationNotFoundError
    if not any(
        message.id == data.assistant_message_id and message.role == "ASSISTANT"
        for message in messages
    ):
        raise AssistantMessageMismatchError

    duplicate = (
        client.table("feedbacks")
        .select("id")
        .eq("user_id", str(user_id))
        .eq("conversation_id", str(data.conversation_id))
        .limit(1)
        .execute()
    )
    if duplicate.data:
        raise ChatFeedbackAlreadyExistsError

    payload = {
        "user_id": str(user_id),
        "rating": data.rating,
        "category": FeedbackCategory.CHATBOT.value,
        "comment": data.comment,
        "conversation_id": str(data.conversation_id),
        "assistant_message_id": str(data.assistant_message_id),
    }
    try:
        response = client.table("feedbacks").insert(payload).execute()
    except APIError as error:
        if "23505" in str(error.args) or "duplicate" in str(error.args).lower():
            raise ChatFeedbackAlreadyExistsError from error
        raise
    rows = response.data or []
    if not rows:
        raise RuntimeError("챗봇 평가 생성 결과가 없습니다.")
    return FeedbackRead.model_validate(rows[0])


def _apply_period(query, start_at: datetime | None, end_at: datetime | None):
    if start_at is not None:
        query = query.gte("created_at", _serialize_utc(start_at))
    if end_at is not None:
        query = query.lte("created_at", _serialize_utc(end_at))
    return query


def list_feedbacks(client: Client, filters: FeedbackFilter) -> FeedbackPage:
    """관리자가 일반 피드백을 조건별로 조회한다."""

    query = (
        client.table("feedbacks")
        .select(FEEDBACK_COLUMNS, count="exact")
        .neq("category", FeedbackCategory.CHATBOT.value)
    )
    if filters.rating is not None:
        query = query.eq("rating", filters.rating)
    if filters.category is not None:
        if filters.category is FeedbackCategory.CHATBOT:
            return FeedbackPage(
                items=[],
                page=filters.page,
                page_size=filters.page_size,
                total=0,
                total_pages=0,
            )
        query = query.eq("category", filters.category.value)
    query = _apply_period(query, filters.start_at, filters.end_at)
    start = (filters.page - 1) * filters.page_size
    response = (
        query.order("created_at", desc=True)
        .range(start, start + filters.page_size - 1)
        .execute()
    )
    total = response.count or 0
    return FeedbackPage(
        items=[FeedbackRead.model_validate(row) for row in response.data or []],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=math.ceil(total / filters.page_size) if total else 0,
    )


def get_feedback(client: Client, feedback_id: UUID) -> FeedbackRead:
    response = (
        client.table("feedbacks")
        .select(FEEDBACK_COLUMNS)
        .eq("id", str(feedback_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise FeedbackNotFoundError
    return FeedbackRead.model_validate(rows[0])


def summarize_chat_feedbacks(
    client: Client,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ChatFeedbackSummary:
    query = (
        client.table("feedbacks")
        .select("rating")
        .eq("category", FeedbackCategory.CHATBOT.value)
    )
    query = _apply_period(query, start_at, end_at)
    ratings = [int(row["rating"]) for row in query.execute().data or []]
    counts = {rating: ratings.count(rating) for rating in range(1, 6)}
    total = len(ratings)
    low_count = counts[1] + counts[2]
    return ChatFeedbackSummary(
        average_rating=round(sum(ratings) / total, 2) if total else None,
        rating_counts=counts,
        total_count=total,
        low_rating_count=low_count,
        low_rating_ratio=round(low_count / total, 4) if total else 0,
    )


def list_chat_feedbacks(
    client: Client,
    filters: ChatFeedbackFilter,
) -> FeedbackPage:
    query = (
        client.table("feedbacks")
        .select(FEEDBACK_COLUMNS, count="exact")
        .eq("category", FeedbackCategory.CHATBOT.value)
        .lte("rating", filters.max_rating)
    )
    if filters.has_comment is True:
        query = query.not_.is_("comment", "null")
    elif filters.has_comment is False:
        query = query.is_("comment", "null")
    if filters.conversation_id is not None:
        query = query.eq("conversation_id", str(filters.conversation_id))
    query = _apply_period(query, filters.start_at, filters.end_at)
    start = (filters.page - 1) * filters.page_size
    response = (
        query.order("rating")
        .order("created_at", desc=True)
        .range(start, start + filters.page_size - 1)
        .execute()
    )
    total = response.count or 0
    return FeedbackPage(
        items=[FeedbackRead.model_validate(row) for row in response.data or []],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=math.ceil(total / filters.page_size) if total else 0,
    )


def get_chat_feedback_detail(
    client: Client,
    feedback_id: UUID,
) -> ChatFeedbackDetail:
    feedback = get_feedback(client, feedback_id)
    if (
        feedback.category is not FeedbackCategory.CHATBOT
        or feedback.conversation_id is None
        or feedback.assistant_message_id is None
    ):
        raise FeedbackNotFoundError

    messages = _conversation_messages(
        client,
        feedback.user_id,
        feedback.conversation_id,
    )
    selected = next(
        (
            message
            for message in messages
            if message.id == feedback.assistant_message_id
            and message.role == "ASSISTANT"
        ),
        None,
    )
    if selected is None:
        raise AssistantMessageMismatchError
    return ChatFeedbackDetail(
        feedback=feedback,
        selected_assistant_message=selected,
        messages=messages,
    )


def review_chat_feedback(
    client: Client,
    feedback_id: UUID,
    reviewer_id: UUID,
    data: ChatFeedbackReview,
) -> FeedbackRead:
    current = get_feedback(client, feedback_id)
    if current.category is not FeedbackCategory.CHATBOT:
        raise FeedbackNotFoundError
    response = (
        client.table("feedbacks")
        .update(
            {
                "issue_type": data.issue_type.value,
                "improvement_note": data.improvement_note,
                "reviewed_by": str(reviewer_id),
                "reviewed_at": datetime.now(timezone.utc)
                .replace(tzinfo=None)
                .isoformat(),
            }
        )
        .eq("id", str(feedback_id))
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise FeedbackNotFoundError
    return FeedbackRead.model_validate(rows[0])
