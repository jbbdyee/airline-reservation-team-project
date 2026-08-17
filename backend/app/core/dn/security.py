import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from app.core.dn.config import settings


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def generate_session_token() -> str:
    # DB의 sessions.token에 저장할 무작위 불투명 토큰. JWT처럼 내용을 담지 않고
    # 순수 식별자 역할만 하므로 서명/디코딩 로직이 필요 없다.
    return secrets.token_urlsafe(32)


def get_session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.SESSION_EXPIRE_MINUTES
    )