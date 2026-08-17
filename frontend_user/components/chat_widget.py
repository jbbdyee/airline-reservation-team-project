import streamlit as st


def render_chat_message(message: dict) -> None:
    with st.chat_message("user"):
        st.write(message["question"])
    with st.chat_message("assistant"):
        st.write(message["answer"])