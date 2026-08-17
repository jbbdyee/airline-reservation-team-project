import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/core/dn/config.py -> parents[3] == backend/
BACKEND_DIR = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=BACKEND_DIR / ".env")


def _get_env(key: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(f"필수 환경변수 {key}가 설정되지 않았습니다. backend/.env를 확인하세요.")
    if value and value.startswith(("your-", "https://your-")):
        raise RuntimeError(f"{key} 값이 .env.example의 예시 값 그대로입니다. 실제 값으로 바꿔주세요.")
    return value # type: ignore


class Settings:
    # Supabase
    SUPABASE_URL: str = _get_env("SUPABASE_URL", required=True)
    SUPABASE_ANON_KEY: str = _get_env("SUPABASE_ANON_KEY", required=True)
    SUPABASE_SERVICE_ROLE_KEY: str = _get_env("SUPABASE_SERVICE_ROLE_KEY", required=True)

    # Gemini
    GEMINI_API_KEY: str = _get_env("GEMINI_API_KEY", required=True)
    GEMINI_MODEL: str = _get_env("GEMINI_MODEL", default="gemini-3.5-flash")

    # 세션 (JWT 미사용, security.py의 opaque 토큰 방식과 짝을 이룸)
    SESSION_EXPIRE_MINUTES: int = int(_get_env("SESSION_EXPIRE_MINUTES", default="60"))


settings = Settings()