"""대시보드 지표 카드 컴포넌트."""

import streamlit as st


def render_metric(label: str, value: str) -> None:
    st.metric(label, value)
