from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest

from app.schemas.dy.feedback_schema import (
    ChatFeedbackCreate,
    ChatFeedbackFilter,
    ChatFeedbackReview,
    FeedbackCreate,
    FeedbackFilter,
)
from app.services.dy.feedback_service import (
    AssistantMessageMismatchError,
    ChatFeedbackAlreadyExistsError,
    create_chat_feedback,
    create_feedback,
    get_chat_feedback_detail,
    list_chat_feedbacks,
    list_feedbacks,
    review_chat_feedback,
    summarize_chat_feedbacks,
)


USER_ID = UUID("00000000-0000-0000-0000-00000000b002")
ADMIN_ID = UUID("00000000-0000-0000-0000-00000000b001")
FEEDBACK_ID = UUID("00000000-0000-0000-0000-200000000001")
CONVERSATION_ID = UUID("00000000-0000-0000-0000-0000000000f1")
USER_MESSAGE_ID = UUID("00000000-0000-0000-0000-100000000001")
ASSISTANT_MESSAGE_ID = UUID("00000000-0000-0000-0000-100000000002")


def feedback_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "id": str(FEEDBACK_ID),
        "user_id": str(USER_ID),
        "rating": 2,
        "category": "CHATBOT",
        "comment": "설명이 부족해요",
        "conversation_id": str(CONVERSATION_ID),
        "assistant_message_id": str(ASSISTANT_MESSAGE_ID),
        "issue_type": None,
        "improvement_note": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": "2026-08-07T03:00:00",
    }
    row.update(overrides)
    return row


def message_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": str(USER_MESSAGE_ID),
            "user_id": str(USER_ID),
            "conversation_id": str(CONVERSATION_ID),
            "role": "USER",
            "content": "예약 취소는 어떻게 해?",
            "created_at": "2026-08-07T02:59:00",
        },
        {
            "id": str(ASSISTANT_MESSAGE_ID),
            "user_id": str(USER_ID),
            "conversation_id": str(CONVERSATION_ID),
            "role": "ASSISTANT",
            "content": "마이페이지에서 취소할 수 있습니다.",
            "created_at": "2026-08-07T03:00:00",
        },
    ]


@dataclass
class FakeResponse:
    data: Any
    count: int | None = None


class FakeQuery:
    def __init__(self, table: str, response: FakeResponse, calls: list) -> None:
        self.table = table
        self.response = response
        self.calls = calls

    @property
    def not_(self):
        self.calls.append((self.table, "not_", None))
        return self

    def _chain(self, method: str, value: Any = None):
        self.calls.append((self.table, method, value))
        return self

    def select(self, value, **kwargs): return self._chain("select", (value, kwargs))
    def insert(self, value): return self._chain("insert", value)
    def update(self, value): return self._chain("update", value)
    def eq(self, column, value): return self._chain("eq", (column, value))
    def neq(self, column, value): return self._chain("neq", (column, value))
    def lte(self, column, value): return self._chain("lte", (column, value))
    def gte(self, column, value): return self._chain("gte", (column, value))
    def is_(self, column, value): return self._chain("is", (column, value))
    def order(self, column, **kwargs): return self._chain("order", (column, kwargs))
    def limit(self, value): return self._chain("limit", value)
    def range(self, start, end): return self._chain("range", (start, end))
    def execute(self): return self.response


class FakeSupabase:
    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> FakeQuery:
        if not self.responses.get(name):
            raise AssertionError(f"{name} 가짜 응답이 부족합니다.")
        return FakeQuery(name, self.responses[name].pop(0), self.calls)


def test_create_general_feedback_uses_authenticated_user() -> None:
    created = feedback_row(
        category="SERVICE",
        conversation_id=None,
        assistant_message_id=None,
        rating=4,
    )
    fake = FakeSupabase({"feedbacks": [FakeResponse([created])]})

    result = create_feedback(
        fake,  # type: ignore[arg-type]
        USER_ID,
        FeedbackCreate(rating=4, category="SERVICE", comment="  편리해요  "),
    )

    inserted = next(call[2] for call in fake.calls if call[:2] == ("feedbacks", "insert"))
    assert inserted["user_id"] == str(USER_ID)
    assert inserted["comment"] == "편리해요"
    assert result.category == "SERVICE"


def test_create_chat_feedback_validates_selected_assistant_message() -> None:
    invalid_messages = [message_rows()[0]]
    fake = FakeSupabase({"chat_messages": [FakeResponse(invalid_messages)]})

    with pytest.raises(AssistantMessageMismatchError):
        create_chat_feedback(
            fake,  # type: ignore[arg-type]
            USER_ID,
            ChatFeedbackCreate(
                conversation_id=CONVERSATION_ID,
                assistant_message_id=ASSISTANT_MESSAGE_ID,
                rating=2,
            ),
        )


def test_create_chat_feedback_blocks_duplicate_conversation() -> None:
    fake = FakeSupabase(
        {
            "chat_messages": [FakeResponse(message_rows())],
            "feedbacks": [FakeResponse([{"id": str(FEEDBACK_ID)}])],
        }
    )

    with pytest.raises(ChatFeedbackAlreadyExistsError):
        create_chat_feedback(
            fake,  # type: ignore[arg-type]
            USER_ID,
            ChatFeedbackCreate(
                conversation_id=CONVERSATION_ID,
                assistant_message_id=ASSISTANT_MESSAGE_ID,
                rating=2,
            ),
        )


def test_create_chat_feedback_sets_chatbot_category() -> None:
    fake = FakeSupabase(
        {
            "chat_messages": [FakeResponse(message_rows())],
            "feedbacks": [FakeResponse([]), FakeResponse([feedback_row()])],
        }
    )

    result = create_chat_feedback(
        fake,  # type: ignore[arg-type]
        USER_ID,
        ChatFeedbackCreate(
            conversation_id=CONVERSATION_ID,
            assistant_message_id=ASSISTANT_MESSAGE_ID,
            rating=2,
            comment="  설명이 부족해요  ",
        ),
    )

    inserted = [call for call in fake.calls if call[:2] == ("feedbacks", "insert")][0][2]
    assert inserted["category"] == "CHATBOT"
    assert inserted["comment"] == "설명이 부족해요"
    assert result.conversation_id == CONVERSATION_ID


def test_list_general_feedback_excludes_chatbot_and_filters() -> None:
    general = feedback_row(
        category="BOOKING",
        conversation_id=None,
        assistant_message_id=None,
    )
    fake = FakeSupabase({"feedbacks": [FakeResponse([general], count=1)]})

    result = list_feedbacks(
        fake,  # type: ignore[arg-type]
        FeedbackFilter(rating=2, category="BOOKING"),
    )

    assert result.total == 1
    assert ("feedbacks", "neq", ("category", "CHATBOT")) in fake.calls
    assert ("feedbacks", "eq", ("category", "BOOKING")) in fake.calls


def test_chat_summary_calculates_rating_distribution() -> None:
    fake = FakeSupabase(
        {"feedbacks": [FakeResponse([{"rating": 1}, {"rating": 2}, {"rating": 5}])]}
    )

    result = summarize_chat_feedbacks(fake)  # type: ignore[arg-type]

    assert result.average_rating == 2.67
    assert result.rating_counts == {1: 1, 2: 1, 3: 0, 4: 0, 5: 1}
    assert result.low_rating_count == 2
    assert result.low_rating_ratio == 0.6667


def test_chat_feedback_list_defaults_to_low_ratings_with_comment() -> None:
    fake = FakeSupabase({"feedbacks": [FakeResponse([feedback_row()], count=1)]})

    result = list_chat_feedbacks(
        fake,  # type: ignore[arg-type]
        ChatFeedbackFilter(has_comment=True),
    )

    assert result.total == 1
    assert ("feedbacks", "lte", ("rating", 2)) in fake.calls
    assert ("feedbacks", "not_", None) in fake.calls
    assert ("feedbacks", "is", ("comment", "null")) in fake.calls


def test_chat_feedback_detail_includes_full_conversation() -> None:
    fake = FakeSupabase(
        {
            "feedbacks": [FakeResponse([feedback_row()])],
            "chat_messages": [FakeResponse(message_rows())],
        }
    )

    result = get_chat_feedback_detail(fake, FEEDBACK_ID)  # type: ignore[arg-type]

    assert result.selected_assistant_message.id == ASSISTANT_MESSAGE_ID
    assert len(result.messages) == 2


def test_review_chat_feedback_saves_admin_classification() -> None:
    reviewed = feedback_row(
        issue_type="INSUFFICIENT",
        improvement_note="FAQ 문맥 보강",
        reviewed_by=str(ADMIN_ID),
        reviewed_at="2026-08-08T03:00:00",
    )
    fake = FakeSupabase(
        {"feedbacks": [FakeResponse([feedback_row()]), FakeResponse([reviewed])]}
    )

    result = review_chat_feedback(
        fake,  # type: ignore[arg-type]
        FEEDBACK_ID,
        ADMIN_ID,
        ChatFeedbackReview(
            issue_type="INSUFFICIENT",
            improvement_note="  FAQ 문맥 보강  ",
        ),
    )

    updated = next(call[2] for call in fake.calls if call[:2] == ("feedbacks", "update"))
    assert updated["reviewed_by"] == str(ADMIN_ID)
    assert updated["improvement_note"] == "FAQ 문맥 보강"
    assert result.issue_type == "INSUFFICIENT"
