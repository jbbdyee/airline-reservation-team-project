
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.exceptions.handlers import register_exception_handlers
from app.routers.dn.auth_router import router as auth_router
from app.routers.dn.chat_router import router as chat_router
from app.routers.dn.user_router import router as user_router
from app.routers.dy.router_factory import build_dy_router
from app.core.dn.dependencies import get_current_user, require_admin


BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/app -> backend/
UPLOAD_DIR = BACKEND_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="aio-01-p1-team5 항공권 예약 API")

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(
    build_dy_router(
        current_user_dependency=get_current_user,
        admin_dependency=require_admin,
        upload_dir=UPLOAD_DIR,
    )
)

app.add_middleware(
    CORSMiddleware,
    # 로컬 개발용. 배포 후에는 실제 streamlit.app URL로 교체 (plan.md 8-7 참고)
    allow_origins=["http://localhost:8501", "http://localhost:8502"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(BACKEND_DIR / "static")), name="static")

# 다음 단계(auth/user/chat 라우터 완성 후)에 여기 추가:
# from app.routers.dn.auth_router import router as auth_router
# app.include_router(auth_router)


@app.get("/")
async def read_root() -> dict:
    return {
        "success": True,
        "data": {"service": "aio-01-p1-team5 API"},
        "message": "ok",
        "error_code": None,
    }


@app.get("/health")
async def health_check() -> dict:
    return {"success": True, "data": {"status": "healthy"}, "message": "ok", "error_code": None}
