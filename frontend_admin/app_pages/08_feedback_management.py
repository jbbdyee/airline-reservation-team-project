"""챗봇 평가 필터·상세·개선 분류 관리 화면."""

from datetime import date

import pandas as pd
import streamlit as st

from clients.feedback_client import (
    get_feedback_detail,
    get_feedbacks,
    get_chat_feedback_detail,
    get_chat_feedback_summary,
    get_chat_feedbacks,
    save_chat_feedback_review,
)
from core.api_client import BackendAPIError


ISSUE_TYPES = ["부정확", "질문 이해 실패", "정보 부족", "응답 지연", "기타"]

st.title("챗봇 평가 관리")
st.caption("일반 서비스 의견과 챗봇 저평점 상담을 함께 관리합니다.")

with st.expander("일반 사용자 피드백 목록·상세", expanded=True):
    try:
        service_feedbacks = get_feedbacks({"page": 1})
    except BackendAPIError as error:
        st.error(str(error))
        service_feedbacks = []

    if service_feedbacks:
        service_column1, service_column2 = st.columns(2)
        service_ratings = service_column1.multiselect(
            "서비스 평점",
            [1, 2, 3, 4, 5],
            default=[1, 2, 3, 4, 5],
        )
        categories = sorted(
            {item.get("category", "기타") for item in service_feedbacks}
        )
        service_category = service_column2.selectbox(
            "서비스 카테고리",
            ["전체", *categories],
        )
        filtered_service_feedbacks = [
            item
            for item in service_feedbacks
            if item.get("rating") in service_ratings
            and (
                service_category == "전체"
                or item.get("category") == service_category
            )
        ]
        st.dataframe(
            pd.DataFrame(filtered_service_feedbacks),
            use_container_width=True,
            hide_index=True,
        )

        if filtered_service_feedbacks:
            service_id = st.selectbox(
                "상세 피드백 선택",
                [item["id"] for item in filtered_service_feedbacks],
                format_func=lambda value: next(
                    f"{item.get('rating')}점 · {item.get('category')} · {item.get('content', '')[:25]}"
                    for item in filtered_service_feedbacks
                    if item["id"] == value
                ),
            )
            try:
                service_detail = get_feedback_detail(service_id)

                detail_rows = [
                    {
                        "항목": "피드백 ID",
                        "내용": service_detail.get("id", "-"),
                    },
                    {
                        "항목": "사용자 ID",
                        "내용": service_detail.get("user_id", "-"),
                    },
                    {
                        "항목": "평점",
                        "내용": f"{service_detail.get('rating', '-')}점",
                    },
                    {
                        "항목": "카테고리",
                        "내용": service_detail.get("category", "-"),
                    },
                    {
                        "항목": "카테고리 코드",
                        "내용": service_detail.get(
                            "category_code",
                            "-",
                        ),
                    },
                    {
                        "항목": "내용",
                        "내용": service_detail.get(
                            "comment",
                            service_detail.get("content", "-"),
                        ),
                    },
                    {
                        "항목": "대화 ID",
                        "내용": service_detail.get(
                            "conversation_id",
                        )
                        or "-",
                    },
                    {
                        "항목": "개선 유형",
                        "내용": service_detail.get("issue_type") or "-",
                    },
                    {
                        "항목": "개선 메모",
                        "내용": service_detail.get(
                            "improvement_note",
                        )
                        or "-",
                    },
                    {
                        "항목": "검토자",
                        "내용": service_detail.get("reviewed_by") or "-",
                    },
                    {
                        "항목": "검토 일시",
                        "내용": service_detail.get("reviewed_at") or "-",
                    },
                    {
                        "항목": "작성 일시",
                        "내용": service_detail.get("created_at", "-"),
                    },
                ]

                st.dataframe(
                    pd.DataFrame(detail_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            except BackendAPIError as error:
                st.error(str(error))
    else:
        st.info("등록된 일반 사용자 피드백이 없습니다.")

st.divider()
st.subheader("챗봇 상담 평가")

with st.container(border=True):
    st.subheader("상담 필터")
    column1, column2, column3, column4 = st.columns(4)
    ratings = column1.multiselect("평점", [1, 2, 3, 4, 5], default=[1, 2])
    period = column2.date_input("작성 기간", value=(date(2026, 8, 1), date.today()))
    comment_option = column3.selectbox("의견 유무", ["전체", "의견 있음", "의견 없음"])
    conversation_id = column4.text_input("대화 ID")
    
start_at, end_at = period if isinstance(period, tuple) and len(period) == 2 else (period, period)
params = {
    "max_rating": max(ratings) if ratings else None,
    "has_comment": True if comment_option == "의견 있음" else False if comment_option == "의견 없음" else None,
    "start_at": str(start_at),
    "end_at": str(end_at),
    "page": 1,
}

try:
    summary = get_chat_feedback_summary(str(start_at), str(end_at))
    feedbacks = get_chat_feedbacks(params)
except BackendAPIError as error:
    st.error(str(error))
    st.stop()

feedbacks = [
    item for item in feedbacks
    if (not ratings or item.get("rating") in ratings)
    and conversation_id.lower() in item.get("conversation_id", "").lower()
    and (comment_option == "전체" or (comment_option == "의견 있음" and item.get("comment")) or (comment_option == "의견 없음" and not item.get("comment")))
]
feedbacks.sort(key=lambda item: (item.get("rating", 5), item.get("created_at", "")))

rating_counts = summary.get("rating_counts", {})
metric_columns = st.columns(7)
metric_columns[0].metric("평균 평점", f"{summary.get('average_rating', 0):.2f}")
metric_columns[1].metric("저평점 비율", f"{summary.get('low_rating_ratio', 0):.1f}%")
for score in range(1, 6):
    metric_columns[score + 1].metric(f"{score}점", f"{rating_counts.get(score, rating_counts.get(str(score), 0))}건")

if not feedbacks:
    st.info("필터 조건에 맞는 챗봇 평가가 없습니다.")
    st.stop()

table_rows = [{
    "평가 ID": item.get("id"),
    "대화 ID": item.get("conversation_id"),
    "평점": item.get("rating"),
    "사용자 의견": item.get("comment", ""),
    "문제 유형": item.get("issue_type", item.get("cause", "")),
    "작성 시각": item.get("created_at", ""),
} for item in feedbacks]
st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

selected_id = st.selectbox(
    "상세 평가 선택",
    [item["id"] for item in feedbacks],
    format_func=lambda value: next(f"{item.get('rating')}점 · {item.get('conversation_id')}" for item in feedbacks if item["id"] == value),
)

try:
    detail = get_chat_feedback_detail(selected_id)
except BackendAPIError as error:
    st.error(str(error))
    st.stop()

st.subheader("상담 상세")
with st.chat_message("user"):
    st.write(detail.get("question", detail.get("user_question", "질문 정보가 없습니다.")))
with st.chat_message("assistant"):
    st.write(detail.get("answer", detail.get("assistant_answer", "AI 답변 정보가 없습니다.")))
st.info(f"사용자 의견: {detail.get('comment') or '작성된 의견 없음'}")
st.write(f"평점: {'★' * detail.get('rating', 0)}{'☆' * (5 - detail.get('rating', 0))}")

if detail.get("rating", 5) <= 2:
    current_issue = detail.get("issue_type", detail.get("cause", ""))
    current_note = detail.get("improvement_note", detail.get("memo", ""))
    with st.form("chat_feedback_review_form"):
        issue_type = st.selectbox("저평점 원인", ISSUE_TYPES, index=ISSUE_TYPES.index(current_issue) if current_issue in ISSUE_TYPES else 0)
        improvement_note = st.text_area("개선 메모", value=current_note, placeholder="재현 조건, 개선 대상과 확인 방법을 작성하세요.")
        submitted = st.form_submit_button("분류 및 개선 메모 저장", use_container_width=True)
    if submitted:
        try:
            save_chat_feedback_review(selected_id, issue_type, improvement_note)
            st.success("검토 결과를 저장했습니다.")
            st.rerun()
        except BackendAPIError as error:
            st.error(str(error))
