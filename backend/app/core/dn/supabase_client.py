
from supabase import Client, create_client

from app.core.dn.config import settings

_client: Client | None = None


def get_supabase_client() -> Client:
    """Supabase client를 생성하고 재사용합니다.

    백엔드 서버 코드에서만 쓰는 클라이언트라 RLS를 우회하는
    service role key를 사용합니다. 이 키는 프론트엔드 코드나
    GitHub에 절대 노출되면 안 됩니다.
    """
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def get_supabase() -> Client:
    """dy Router에서 FastAPI 의존성으로 사용하는 Supabase client 별칭."""
    return get_supabase_client()
