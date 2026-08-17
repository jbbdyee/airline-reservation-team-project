import streamlit as st

from clients.feedback_client import (
    create_feedback,
    create_service_feedback,
    is_feedback_submitted,
)
from core.api_client import BackendAPIError
from core.auth import require_login


def is_valid_comment(comment: str) -> bool:
    """의견이 공백을 제외하고 2글자 이상인지 확인합니다."""

    return len(comment.strip()) >= 2


require_login()

st.title("피드백")

user_id = st.session_state["user"]["user_id"]

chat_tab, service_tab = st.tabs(
    ["챗봇 답변 평가", "서비스 만족도"]
)

with chat_tab:
    messages = st.session_state.get("chat_messages", [])

    if not messages:
        st.info("평가할 챗봇 답변이 없습니다.")

        st.page_link(
            "app_pages/06_chat.py",
            label="AI 여행 도우미로 이동",
        )

    else:
        message = messages[-1]
        message_id = message["message_id"]

        st.subheader("최근 질문")
        st.write(message["question"])

        st.subheader("챗봇 답변")
        st.info(message["answer"])

        if is_feedback_submitted(user_id, message_id):
            st.success(
                "이 챗봇 답변은 이미 평가 완료되었습니다."
            )

        else:
            with st.form("chat_feedback_form"):
                score = st.slider(
                    "만족도",
                    min_value=1,
                    max_value=5,
                    value=5,
                    key="chat_score",
                )

                comment = st.text_area(
                    "의견",
                    max_chars=1000,
                    placeholder="답변에 대한 의견을 2글자 이상 입력해 주세요.",
                    key="chat_comment",
                )

                submitted = st.form_submit_button(
                    "챗봇 평가 제출",
                    type="primary",
                )

            if submitted:
                comment = comment.strip()

                if not is_valid_comment(comment):
                    st.warning("의견은 2글자 이상 입력해 주세요.")

                else:
                    try:
                        create_feedback(
                            user_id=user_id,
                            message_id=message_id,
                            score=score,
                            comment=comment,
                        )

                        st.success("챗봇 평가가 저장되었습니다.")
                        st.rerun()

                    except BackendAPIError as error:
                        st.error(str(error))


with service_tab:
    st.subheader("서비스 만족도")

    st.caption(
        "항공편 검색, 좌석 선택, 예약 기능에 대한 "
        "의견을 남겨 주세요."
    )

    with st.form("service_feedback_form"):
        score = st.slider(
            "서비스 만족도",
            min_value=1,
            max_value=5,
            value=5,
            key="service_score",
        )

        comment = st.text_area(
            "의견",
            max_chars=1000,
            placeholder="서비스 이용 의견을 2글자 이상 입력해 주세요.",
            key="service_comment",
        )

        submitted = st.form_submit_button(
            "서비스 피드백 제출",
            type="primary",
        )

    if submitted:
        comment = comment.strip()

        if not is_valid_comment(comment):
            st.warning("의견은 2글자 이상 입력해 주세요.")

        else:
            try:
                create_service_feedback(
                    user_id=user_id,
                    score=score,
                    comment=comment,
                )

                st.success("서비스 피드백이 저장되었습니다.")

            except BackendAPIError as error:
                st.error(str(error))