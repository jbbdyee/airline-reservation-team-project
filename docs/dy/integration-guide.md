# 백엔드 통합 가이드

이 문서는 공통 기반 소유자(dn)의 인증·사용자·챗봇 기능과 dy API가 최종
애플리케이션에서 어떻게 통합되었는지 설명한다.

## 1. 인증 의존성 계약

dy Router 팩토리는 아래 두 callable을 요구한다.

- `current_user_dependency`: 유효한 로그인 세션을 검사하고 사용자 객체를 반환한다.
- `admin_dependency`: 로그인 세션과 `role == "ADMIN"`을 검사하고 관리자 객체를 반환한다.

반환 객체에는 `id` 또는 `user_id` UUID 필드가 있어야 한다. dict와 Pydantic
객체를 모두 지원한다. 인증 실패는 401, 관리자 권한 부족은 403으로 처리한다.

권장 함수명은 다음과 같다.

```python
def get_current_user(...):
    ...

def require_admin(...):
    ...
```

## 2. main.py 통합 결과

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.dn.dependencies import get_current_user, require_admin
from app.exceptions.handlers import register_exception_handlers
from app.routers.dn.auth_router import router as auth_router
from app.routers.dn.chat_router import router as chat_router
from app.routers.dn.user_router import router as user_router
from app.routers.dy.router_factory import build_dy_router

app = FastAPI(title="aio-01-p1-team5 항공권 예약 API")

backend_dir = Path(__file__).resolve().parent.parent
upload_dir = backend_dir / "static" / "uploads"
upload_dir.mkdir(parents=True, exist_ok=True)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(
    build_dy_router(
        current_user_dependency=get_current_user,
        admin_dependency=require_admin,
        upload_dir=upload_dir,
    )
)

register_exception_handlers(app)
app.mount("/static/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")
app.mount("/static", StaticFiles(directory=str(backend_dir / "static")), name="static")
```

실제 `main.py`에는 로컬 사용자·관리자 Streamlit 앱을 위한 CORS 설정과 `/`,
`/health` 엔드포인트도 포함되어 있다. dn Router와 dy Router는 동일한 FastAPI
애플리케이션에 등록되며, dy Router에는 실제 인증 의존성이 주입된다.

## 3. 공통 예외 형식

인증 오류와 FastAPI 검증 오류도 다음 형식을 사용해야 한다.

```json
{
  "success": false,
  "data": null,
  "message": "요청값을 확인해 주세요.",
  "error_code": "VALIDATION_ERROR"
}
```

`RequestValidationError`, `HTTPException`, 예상하지 못한 서버 오류와 DB 연결 오류를
`backend/app/exceptions/handlers.py`에서 공통 형식으로 변환한다. 비밀번호, 세션
토큰, 내부 SQL과 stack trace는 응답 또는 운영 로그에 출력하지 않는다.

## 4. DB 적용 순서

신규 DB:

1. `backend/sql/dn/schema.sql`
2. `backend/sql/dn/seed.sql`(비어 있는 개발 DB에 최초 1회만)
3. `backend/sql/dy/booking_rpcs.sql`

기존 DB에 `bookings.cancel_reason`이 없는 경우:

1. `backend/sql/dy/add_booking_cancel_reason.sql`
2. `backend/sql/dy/booking_rpcs.sql`

신규 스키마에는 `cancel_reason`이 이미 포함되어 있으므로 마이그레이션 SQL을
별도로 실행할 필요가 없다. 기존 DB용 마이그레이션은 컬럼을 추가하고 기존
취소 이벤트의 사유를 가능한 범위에서 예약 데이터로 이관한다.

RPC 적용 후 Supabase 함수 목록에서 다음 함수를 확인한다.

- `create_booking_atomic`
- `cancel_booking_atomic`
- `set_booking_status_atomic`

## 5. 통합 확인

```powershell
$env:PYTHONPATH="backend"
python -m pytest -q backend/tests/dy frontend_admin/tests
uvicorn app.main:app --app-dir backend --reload
```

확인 항목:

- `/docs`에 dy API 경로와 메서드가 모두 표시된다.
- 인증 없이 예약·피드백·업로드·SSE 호출 시 401이다.
- 일반 사용자가 `/admin/*` 및 항공편·좌석 변경 API를 호출하면 403이다.
- `/static/uploads/<filename>`으로 업로드 이미지가 조회된다.
- 같은 좌석의 병렬 예약 요청 중 하나만 201이고 나머지는 409이다.
- 예약·취소·상태 변경 후 `event_logs`와 SSE에 동일 이벤트가 표시된다.
- 예약 취소 사유가 `bookings.cancel_reason`에 저장되고 취소 이벤트에도 반영된다.

## 6. 최종 통합 범위

- 인증·사용자·챗봇 Router와 dy Router의 단일 FastAPI 앱 등록
- 공항·항공편·좌석 조회 및 관리자 CRUD
- 예약 생성·조회·취소와 관리자 예약 상태 변경
- 프로필 이미지 업로드와 정적 파일 제공
- 일반 서비스 피드백, 챗봇 상담 평가, 관리자 검토 결과 저장
- 관리자 운영 지표, 이벤트 로그 목록·상세, SSE 스트림
- 공통 성공·오류 응답과 인증·권한 검증

백엔드는 `GET /events/stream` SSE를 제공한다. 현재 관리자 실시간 모니터 화면은
Streamlit fragment를 이용해 3초마다 이벤트 로그를 다시 조회하며, SSE URL 생성
기능은 클라이언트에 별도로 준비되어 있다.
