# SkyOps 관리자 프론트엔드

항공권 예약 서비스의 운영 관리자용 Streamlit 앱입니다. 관리자 로그인과 권한 차단, 운영 대시보드, 항공편·좌석·예약·사용자 관리, 이벤트 로그, 챗봇 평가 분석을 제공합니다.

## 실행

```powershell
python -m pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

기본값은 백엔드 없이 실행되는 데모 모드입니다.

- 관리자: `admin@skyops.dev` / `admin1234`
- 권한 차단 확인용 사용자: `user@skyops.dev` / `user1234`

실제 백엔드와 연결하려면 환경 변수 `DEMO_MODE=false`, `BACKEND_BASE_URL=http://127.0.0.1:8000`을 설정합니다. 모든 HTTP 호출은 `api/client.py`를 거치며 Bearer 토큰, 공통 `data` 응답 래핑, `BackendAPIError`를 일관되게 처리합니다.

## 구조

```text
app.py                 실행, 테마, 내비게이션, 권한 게이트
api/                   공통 HTTP Client와 BackendAPIError
clients/               도메인별 백엔드 API 어댑터
core/                  인증 세션 및 데모 저장소
components/            재사용 가능한 표시 컴포넌트 확장 위치
app_pages/             관리자 기능별 화면
.streamlit/config.toml 공통 스카이 블루 테마
```

## 백엔드 연동 계약

현재 클라이언트가 기대하는 경로는 아래와 같습니다. 팀 API 명세가 변경되면 각 `clients/*_client.py`의 경로만 조정하면 됩니다.

- `POST /auth/signin`, `POST /auth/signout`
- `GET|POST /flights`, `PUT|DELETE /flights/{flight_id}`
- `GET|POST /flights/{flight_id}/seats`, `PUT|DELETE /seats/{seat_id}`
- `GET /admin/bookings`, `PUT /admin/bookings/{booking_id}/status`
- `GET /admin/users`, `PUT /admin/users/{user_id}/role`
- `GET /admin/event-logs`, `GET /admin/event-logs/{event_log_id}`, `GET /events/stream`
- `GET /admin/feedbacks`, `GET /admin/feedbacks/{feedback_id}`
- `GET /admin/chat-feedbacks/summary`, `GET /admin/chat-feedbacks`, `GET /admin/chat-feedbacks/{feedback_id}`
- `PUT /admin/chat-feedbacks/{feedback_id}/review`

운영 환경에서는 프론트엔드의 세션 권한 차단과 별개로 모든 `/admin` API가 백엔드에서 관리자 역할을 다시 검증해야 합니다.
