import streamlit as st

from clients.auth_client import update_profile
from core.api_client import BackendAPIError
from core.auth import require_login


require_login()

user = st.session_state["user"]

st.title("프로필")

# 저장 직후 한 번만 성공 메시지를 표시한다.
if st.session_state.pop("profile_saved", False):
    st.success("프로필이 저장되었습니다.")

name = st.text_input(
    "이름",
    value=user["name"],
)

image = st.file_uploader(
    "프로필 이미지",
    type=["png", "jpg", "jpeg"],
)

if image is not None:
    st.image(
        image,
        caption=f"선택한 이미지: {image.name}",
        width=200,
    )

elif user.get("profile_image"):
    st.caption(
        f"현재 저장된 이미지 파일: {user['profile_image']}"
    )

if st.button("프로필 저장", type="primary"):
    try:
        profile_image = (
            image
            if image is not None
            else user.get("profile_image", "")
        )

        st.session_state["user"] = update_profile(
            user_id=user["user_id"],
            name=name,
            profile_image=profile_image,
        )

        st.session_state["profile_saved"] = True
        st.rerun()

    except BackendAPIError as error:
        st.error(str(error))