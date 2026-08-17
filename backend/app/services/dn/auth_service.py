from app.core.dn.security import (
    generate_session_token,
    get_session_expiry,
    hash_password,
    verify_password,
)
from app.core.dn.supabase_client import get_supabase_client
from app.exceptions.handlers import AppException
from app.schemas.dn.auth_schema import SigninResponse, SignupRequest, UserPublic


def signup(payload: SignupRequest) -> UserPublic:
    supabase = get_supabase_client()

    existing = (
        supabase.table("users")
        .select("id")
        .eq("email", payload.email)
        .execute()
    )
    if existing.data:
        raise AppException(409, "EMAIL_ALREADY_EXISTS", "이미 가입된 이메일입니다.")

    result = (
        supabase.table("users")
        .insert(
            {
                "email": payload.email,
                "password_hash": hash_password(payload.password),
                "name": payload.name,
                "role": "USER",
            }
        )
        .execute()
    )
    if not result.data:
        raise AppException(500, "SIGNUP_FAILED", "회원가입에 실패했습니다.")

    return UserPublic(**result.data[0])


def signin(email: str, password: str) -> SigninResponse:
    supabase = get_supabase_client()

    result = (
        supabase.table("users")
        .select("id, email, password_hash, name, phone, role, profile_image_url, created_at")
        .eq("email", email)
        .execute()
    )
    user = result.data[0] if result.data else None
    if user is None or not verify_password(password, user["password_hash"]):
        raise AppException(401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.")

    token = generate_session_token()
    expires_at = get_session_expiry()

    supabase.table("sessions").insert(
        {
            "token": token,
            "user_id": user["id"],
            "expires_at": expires_at.isoformat(),
        }
    ).execute()

    user_public = UserPublic(**{k: v for k, v in user.items() if k != "password_hash"})
    return SigninResponse(user=user_public, session_token=token, expires_at=expires_at)


def signout(token: str) -> None:
    supabase = get_supabase_client()
    supabase.table("sessions").delete().eq("token", token).execute()