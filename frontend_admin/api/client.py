"""기존 import 경로 호환 모듈."""

from core.api_client import BACKEND_URL, BackendAPIError, as_list, request

__all__ = ["BACKEND_URL", "BackendAPIError", "as_list", "request"]
