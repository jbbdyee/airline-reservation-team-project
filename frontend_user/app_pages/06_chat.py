import streamlit as st

from clients.chat_client import send_message
from components.chat_widget import render_chat_message
from core.api_client import BackendAPIError


def render_chat_input() -> tuple[bool, str]:
    """화면 하단에 고정되는 채팅 입력창과 전송 버튼을 표시합니다."""

    with st.form(
        "chat_input_form",
        clear_on_submit=True,
        border=False,
    ):
        input_column, send_column = st.columns([20, 1])

        with input_column:
            question = st.text_input(
                "질문",
                placeholder="질문을 입력해 주세요. (최대 500자)",
                label_visibility="collapsed",
            )

        with send_column:
            submitted = st.form_submit_button(
                "↑",
                type="secondary",
                use_container_width=True,
            )

    return submitted, question.strip()


st.markdown(
    """
    <style>
        /* chat_input_form에만 적용되는 하단 고정 스타일 */
        .st-key-chat_input_form {
            z-index: 1000 !important;
            bottom: 1.5rem !important;
            left: 25% !important;
            right: 5rem !important;
            width: auto !important;
            margin: 0 !important;
            padding: 0.5rem 0.75rem !important;
            border-radius: 0.75rem !important;
            background: #f0f2f6 !important;
        }

        
        .st-key-chat_input_form div[data-testid="stTextInput"] input {
            min-height: 2.5rem !important;
            border: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }

        .st-key-chat_input_form div[data-testid="stTextInput"] input:focus {
            border: 0 !important;
            box-shadow: none !important;
        }

        .st-key-chat_input_form button {
            min-width: 2.5rem !important;
            height: 2.5rem !important;
            padding: 0 !important;
            border: 0 !important;
            border-radius: 0.5rem !important;
            background: #dfe3eb !important;
            color: #8a93a3 !important;
            font-size: 1.5rem !important;
        }

        .st-key-chat_input_form button:hover {
            background: #cfd5df !important;
            color: #4b5563 !important;
        }

        @media (max-width: 900px) {
            .st-key-chat_input_form {
                left: 1rem !important;
                right: 1rem !important;
                bottom: 1rem !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AI 여행 도우미")

st.caption(
    "항공편 검색, 좌석 선택, 예약, 예약 취소 방법을 물어보세요."
)

messages = st.session_state.setdefault("chat_messages", [])
chat_ended = st.session_state.get("chat_ended", False)

# 상담 종료 후에는 종료 안내만 표시하고 입력은 막는다.
# 상담 종료 후에는 종료 안내와 재상담 시작 버튼을 표시한다.
if chat_ended:
    st.info("상담을 종료했습니다.")

    if st.button(
        "재상담 시작",
        type="primary",
    ):
        # 이전 대화와 대화 ID를 초기화하고 새 상담을 시작한다.
        st.session_state["chat_messages"] = []
        st.session_state.pop("chat_conversation_id", None)
        st.session_state["chat_ended"] = False
        st.rerun()

    st.stop()

# 중앙 영역에 기존 채팅 기록을 표시한다.
for message in messages:
    render_chat_message(message)

# 새 메시지와 답변 대기 화면을 중앙 채팅 영역에 표시할 자리
pending_chat = st.empty()

# 채팅 입력란 바로 위, 오른쪽의 상담 종료 버튼
_, right_column = st.columns([5, 1])

with right_column:
    if st.button(
        "상담 종료",
        type="secondary",
        use_container_width=True,
    ):
        st.session_state["chat_ended"] = True
        st.rerun()

# 화면 하단 고정 채팅 입력창
submitted, question = render_chat_input()

if submitted:
    if not question:
        st.warning("내용을 입력해 주세요.")

    elif len(question) < 2:
        st.warning("2글자 이상 입력해 주세요.")

    else:
        try:
            with pending_chat.container():
                # 사용자가 입력한 질문을 먼저 화면에 표시
                with st.chat_message("user"):
                    st.write(question)

                # 답변을 기다리는 동안 스피너 표시
                with st.chat_message("assistant"):
                    with st.spinner("답변을 생성하고 있습니다..."):
                        message = send_message(
                            question,
                            conversation_id=st.session_state.get(
                                "chat_conversation_id"
                            ),
                        )

            messages.append(message)
            st.session_state["chat_conversation_id"] = message[
                "conversation_id"
            ]
            st.rerun()

        except BackendAPIError as error:
            st.error(str(error))

# 로그인 사용자만 챗봇 답변 평가 페이지로 이동할 수 있다.
if messages and st.session_state.get("user"):
    st.page_link(
        "app_pages/08_feedback.py",
        label="최근 챗봇 답변 평가하기",
        icon="⭐",
    )