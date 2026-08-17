# API 명세

작성·검수: dy  
이 문서는 최종 FastAPI Router·Schema·Service와 사용자·관리자 프론트엔드
클라이언트가 사용하는 API 계약을 정리한다.   
`plan.md`와 실제 구현이 다른
부분은 현재 프론트엔드 연동 방식을 기준으로 기록한다.

## 1. 공통 규칙

- 기준 URL: `/`
- 요청·응답의 시간은 ISO 8601 UTC 형식을 사용한다. 예: `2026-08-07T03:00:00Z`
- ID는 UUID 문자열이며 이벤트 로그 ID만 정수이다.
- 인증 API는 `Authorization: Bearer <session-token>` 헤더를 사용한다.
- 관리자 API는 로그인과 `ADMIN` 역할을 모두 요구한다.
- 페이지 번호는 1부터 시작하며 기본값은 `1`, 기본 `page_size`는 `20`이다.
- 삭제 성공은 본문 없는 `204 No Content`를 반환한다.
- 날짜·열거형·필수값 검증 실패는 등록된 공통 예외 Handler가 공통 오류 형식으로 변환한다.
- dy Router는 `get_current_user`, `require_admin` 의존성을 주입받아 인증과 관리자 권한을 검사한다.

### 공통 성공 응답

```json
{
  "success": true,
  "data": {},
  "message": "요청이 성공적으로 처리되었습니다.",
  "error_code": null
}
```

### 공통 실패 응답

```json
{
  "success": false,
  "data": null,
  "message": "요청한 항공편을 찾을 수 없습니다.",
  "error_code": "FLIGHT_NOT_FOUND"
}
```

### 페이지 응답의 `data`

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

## 2. 공항 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/airports` | 불필요 | 공항 목록 또는 키워드 검색 |

`GET /airports`

- Query: `keyword`(선택, IATA 코드·공항명·도시명 검색)
- 200 `data`: `[{id, iata_code, name, city, country}]`
- 검색 결과가 없어도 200과 빈 배열을 반환한다.

## 3. 항공편 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/flights` | 불필요 | 항공편 조건 검색 |
| GET | `/flights/{flight_id}` | 불필요 | 항공편 상세 조회 |
| GET | `/admin/flights` | 관리자 | 관리자 항공편 목록 |
| POST | `/flights` | 관리자 | 항공편 생성 |
| PUT | `/flights/{flight_id}` | 관리자 | 항공편 수정 |
| DELETE | `/flights/{flight_id}` | 관리자 | 항공편 삭제 |

`GET /flights`

- 필수 Query: `origin`, `destination`, `date`, `passengers`, `cabin_class`
- `origin`, `destination`: IATA 코드
- `date`: `YYYY-MM-DD`
- `passengers`: 1 이상 9 이하
- `cabin_class`: `ECONOMY | BUSINESS`
- 선택 Query: `sort_by=price|departure_at`, `sort_order=asc|desc`
- 200 `data`: 검색 조건과 좌석 수를 만족하는 항공편 목록
- 항목: `id`, `flight_number`, `origin`, `destination`, `departure_at`, `arrival_at`, `status`, `base_price`, `lowest_seat_price`, `available_seats`

`GET /flights/{flight_id}`

- 200 `data`: 목록 항목 + `seats_by_cabin_class`
- 404: `FLIGHT_NOT_FOUND`

`GET /admin/flights`

- 선택 Query: `flight_number`, `status`, `page`, `page_size`
- `status`: `SCHEDULED | DELAYED | CANCELLED | DEPARTED`
- 편명은 일부 문자열로 검색하며 출발시각 최신순 페이지 응답을 반환한다.
- 잔여 좌석이 없는 항공편과 결항·출발 완료 항공편도 관리자 목록에 포함한다.

`POST /flights`

- Body: `flight_number`, `origin_airport_id`, `destination_airport_id`, `departure_at`, `arrival_at`, `status`, `base_price`
- 201: 생성된 항공편
- 409: `FLIGHT_CONFLICT`
- 422: 출발/도착 공항 동일, 잘못된 시간·가격·상태

`PUT /flights/{flight_id}`

- Body: 생성 필드 중 변경할 필드만 전달
- 200: 수정된 항공편
- 404: `FLIGHT_NOT_FOUND`
- 운항 상태가 바뀌면 `FLIGHT_STATUS_CHANGED` 이벤트를 생성한다.

`DELETE /flights/{flight_id}`

- 204: 삭제 성공
- 404: `FLIGHT_NOT_FOUND`
- 409: 연결된 좌석이나 예약으로 삭제할 수 없음, `FLIGHT_IN_USE`

## 4. 좌석 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/flights/{flight_id}/seats` | 불필요 | 항공편 좌석 목록 |
| POST | `/flights/{flight_id}/seats` | 관리자 | 좌석 생성 |
| PUT | `/seats/{seat_id}` | 관리자 | 좌석 수정 |
| DELETE | `/seats/{seat_id}` | 관리자 | 좌석 삭제 |

- 좌석 항목: `id`, `flight_id`, `seat_number`, `cabin_class`, `price`, `status`
- 목록 Query: `cabin_class`(선택)
- 생성 Body: `seat_number`, `cabin_class`, `price`, `status`(기본 `AVAILABLE`)
- 수정 Body: 생성 필드 중 변경할 필드
- 404: `FLIGHT_NOT_FOUND` 또는 `SEAT_NOT_FOUND`
- 409: 좌석 번호 중복 `SEAT_ALREADY_EXISTS`, 예약된 좌석 변경/삭제 `SEAT_IN_USE`
- 좌석 변경은 `SEAT_CHANGED` 이벤트를 생성한다.

## 5. 예약 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| POST | `/bookings` | 사용자 | 예약 생성 |
| GET | `/bookings/me` | 사용자 | 내 예약 목록 |
| GET | `/bookings/{booking_id}` | 사용자 | 본인 예약 상세 |
| PUT | `/bookings/{booking_id}/cancel` | 사용자 | 내 예약 취소 |
| GET | `/admin/bookings` | 관리자 | 전체 예약 목록 |
| PUT | `/admin/bookings/{booking_id}/status` | 관리자 | 예약 상태 변경 |

`POST /bookings`

- Body: `flight_id`, `seat_id`, `passenger_name`
- 201 `data`: `id`, `booking_code`, `user_id`, `flight`, `seat`, `passenger_name`, `status`, `total_price`, `created_at`, `cancelled_at`, `cancel_reason`
- 좌석 확인, 예약 INSERT, 좌석 `BOOKED` 변경을 단일 트랜잭션/RPC로 처리한다.
- 404: `FLIGHT_NOT_FOUND` 또는 `SEAT_NOT_FOUND`
- 409: `SEAT_ALREADY_BOOKED`, `FLIGHT_NOT_BOOKABLE`, `FLIGHT_SEAT_MISMATCH`

`GET /bookings/me`

- Query: `status`(선택), `page`, `page_size`
- 200: 페이지 응답

`GET /bookings/{booking_id}`

- 일반 사용자는 본인 예약만 조회한다.
- 관리자는 `/admin/bookings`에서 전체 예약 정보를 조회한다.
- 403: `BOOKING_ACCESS_DENIED`
- 404: `BOOKING_NOT_FOUND`

`PUT /bookings/{booking_id}/cancel`

- Body: `reason`(선택, 최대 500자)
- 200: 취소된 예약; `cancel_reason`을 저장하고 좌석은 `AVAILABLE`로 복원한다.
- 409: `BOOKING_ALREADY_CANCELLED` 또는 `BOOKING_NOT_CANCELLABLE`

`GET /admin/bookings`

- Query: `status`, `page`, `page_size`
- 200: 전체 예약 페이지 응답

`PUT /admin/bookings/{booking_id}/status`

- Body: `status` (`CONFIRMED | CANCELLED`)
- 200: 변경된 예약
- 예약 생성·취소·상태 변경은 `BOOKING_CHANGED` 이벤트를 생성한다.

## 6. 관리자 대시보드 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/admin/dashboard` | 관리자 | 운영 및 챗봇 품질 지표 |

- 선택 Query: `start_at`, `end_at`
- 200 `data`: `flights`, `bookings`, `chat_feedbacks`, `recent_events`

```json
{
  "flights": {
    "total": 4,
    "scheduled": 2,
    "delayed": 1,
    "cancelled": 1,
    "departed": 0
  },
  "bookings": {
    "total": 3,
    "confirmed": 2,
    "cancelled": 1,
    "confirmed_revenue": 154000
  },
  "chat_feedbacks": {
    "average_rating": 3.0,
    "rating_counts": {"1": 1, "2": 1, "3": 0, "4": 1, "5": 1},
    "total_count": 4,
    "low_rating_count": 2,
    "low_rating_ratio": 0.5
  },
  "recent_events": []
}
```

## 7. 이미지 업로드 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| POST | `/uploads/images` | 사용자 | 프로필 이미지 업로드 |

- Multipart: `file`
- 허용 MIME: `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- 최대 크기: 5 MiB
- 201 `data`: `url`, `filename`, `content_type`, `size`
- 400: `UNSUPPORTED_IMAGE_TYPE`, `IMAGE_TOO_LARGE`, `INVALID_IMAGE`

## 8. 이벤트 및 로그 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/events/stream` | 사용자/관리자 | SSE 이벤트 스트림 |
| GET | `/admin/event-logs` | 관리자 | 이벤트 로그 조회 |
| GET | `/admin/event-logs/{event_log_id}` | 관리자 | 이벤트 로그 상세 |

`GET /events/stream`

- 선택 Query: `flight_id`, `last_event_id`
- 재연결 Header: `Last-Event-ID`; Query와 Header가 모두 있으면 Query가 우선한다.
- Content-Type: `text/event-stream`
- 이벤트 이름: `flight_status_changed`, `seat_changed`, `booking_changed`, `heartbeat`
- 이벤트 `data`: `id`, `event_type`, `resource_id`, `flight_id`, `booking_id`, `actor_user_id`, `payload`, `created_at`

`GET /admin/event-logs`

- Query: `event_type`, `flight_id`, `booking_id`, `start_at`, `end_at`, `page`, `page_size`
- 200: 최신순 페이지 응답
- `event_type`: `FLIGHT_STATUS_CHANGED | SEAT_CHANGED | BOOKING_CHANGED`

`GET /admin/event-logs/{event_log_id}`

- 200: `id`, `event_type`, `resource_id`, `flight_id`, `booking_id`, `actor_user_id`, `payload`, `created_at`
- 404: `EVENT_LOG_NOT_FOUND`

## 9. 일반 피드백 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| POST | `/feedbacks` | 사용자 | 일반 피드백 등록 |
| GET | `/admin/feedbacks` | 관리자 | 일반 피드백 목록 |
| GET | `/admin/feedbacks/{feedback_id}` | 관리자 | 피드백 상세 |

- 등록 Body: `rating`(1~5), `category`(`SERVICE | SEARCH | BOOKING | ETC`), `comment`(선택, 최대 1000자)
- 관리자 목록 Query: `rating`, `category`, `start_at`, `end_at`, `page`, `page_size`
- 201: 생성된 피드백
- 404: `FEEDBACK_NOT_FOUND`

## 10. 챗봇 평가 API

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| POST | `/chat/feedbacks` | 사용자 | 상담 평가 등록 |
| GET | `/admin/chat-feedbacks/summary` | 관리자 | 평가 집계 |
| GET | `/admin/chat-feedbacks` | 관리자 | 저평점 상담 목록 |
| GET | `/admin/chat-feedbacks/{feedback_id}` | 관리자 | 평가와 대화 상세 |
| PUT | `/admin/chat-feedbacks/{feedback_id}/review` | 관리자 | 개선 분류 저장 |

`POST /chat/feedbacks`

- 필수 Body: `conversation_id`, `assistant_message_id`, `rating`(1~5)
- 선택 Body: `comment`
- 201: `category=CHATBOT`인 피드백
- 본인 상담과 해당 상담에 포함된 assistant 메시지만 연결할 수 있다.
- 409: 같은 상담을 이미 평가함, `CHAT_FEEDBACK_ALREADY_EXISTS`

`GET /admin/chat-feedbacks/summary`

- Query: `start_at`, `end_at`
- 200 `data`: `average_rating`, `rating_counts`, `total_count`, `low_rating_count`, `low_rating_ratio`

`GET /admin/chat-feedbacks`

- Query: `max_rating`(기본 2), `has_comment`, `conversation_id`, `start_at`, `end_at`, `page`, `page_size`
- 200: 저평점 우선 페이지 응답

`GET /admin/chat-feedbacks/{feedback_id}`

- 200: 피드백 정보, 선택된 AI 답변, 동일 상담의 사용자 질문·AI 답변 목록
- 404: `FEEDBACK_NOT_FOUND`

`PUT /admin/chat-feedbacks/{feedback_id}/review`

- Body: `issue_type` (`INACCURATE | MISUNDERSTOOD | INSUFFICIENT | SLOW | ETC`), `improvement_note`
- 200: `reviewed_by`, `reviewed_at`이 포함된 검토 결과

## 11. 공통 상태 코드와 오류 코드

| HTTP | 의미 | 대표 오류 코드 |
|---|---|---|
| 400 | 파일·요청 내용 오류 | `INVALID_IMAGE`, `INVALID_REQUEST` |
| 401 | 로그인 필요/세션 만료 | `AUTHENTICATION_REQUIRED`, `SESSION_EXPIRED` |
| 403 | 권한 또는 소유권 없음 | `ADMIN_REQUIRED`, `BOOKING_ACCESS_DENIED` |
| 404 | 리소스 없음 | `FLIGHT_NOT_FOUND`, `SEAT_NOT_FOUND`, `BOOKING_NOT_FOUND`, `FEEDBACK_NOT_FOUND` |
| 409 | 현재 상태·무결성 충돌 | `SEAT_ALREADY_BOOKED`, `BOOKING_ALREADY_CANCELLED`, `RESOURCE_IN_USE` |
| 422 | 필드 형식·범위 검증 실패 | `VALIDATION_ERROR` |
| 500 | 예상하지 못한 서버 오류 | `INTERNAL_SERVER_ERROR` |
| 503 | DB 등 의존 서비스 장애 | `DATABASE_UNAVAILABLE` |

## 12. 프런트엔드 전달 규칙

- 사용자 앱은 공항·항공편 검색, 좌석, 예약, 업로드, 피드백 API를 사용한다.
- 관리자 앱은 `/admin/flights`, 좌석 관리, `/admin/bookings`, 로그·피드백·대시보드 API를 사용한다.
- 인증 요청에는 `Authorization: Bearer <session-token>`을 전달한다.
- `start_at`, `end_at`에는 UTC offset을 포함한다. 예: `2026-08-08T00:00:00+09:00`.
- 업로드는 JSON이 아니라 `multipart/form-data`이며 파일 필드명은 `file`이다.
- 목록 응답은 `data.items`와 `data.page`, `data.page_size`, `data.total`, `data.total_pages`를 사용한다.
- 백엔드는 SSE 재연결용 `last_event_id` Query와 `Last-Event-ID` Header를 지원한다.
- 현재 관리자 실시간 모니터는 SSE 직접 구독 대신 `GET /admin/event-logs`를 3초마다 다시 조회한다.
- 현재 운영 대시보드는 기간 파라미터 없이 `/admin/dashboard`를 호출하고 전체 기간 지표를 표시한다.
- 401은 Session State를 비운 뒤 로그인 화면으로 이동하고, 403은 권한 부족을 안내한다.
- 409는 최신 좌석·예약 상태를 다시 조회한 뒤 사용자에게 재선택 또는 재시도를 안내한다.
- 사용자 피드백 화면은 서비스 카테고리를 직접 선택하지 않고 서비스 만족도는 `SERVICE`로 저장한다.
