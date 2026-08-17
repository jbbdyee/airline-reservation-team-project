# dn 백엔드 API 명세

> 대상: 인증, 사용자, Gemini 챗봇 API  
> Base URL(로컬): `http://127.0.0.1:8000`

## 공통 규칙

### 인증

로그인이 필요한 API는 다음 HTTP 헤더를 사용한다.

```http
Authorization: Bearer {session_token}
```

`session_token`은 `POST /auth/signin` 성공 응답에서 발급된다. 세션은
`sessions` 테이블에 저장하는 불투명(opaque) 토큰 방식이며 JWT가 아니다.

### 오류 응답 형식

모든 dn 오류 응답은 아래 형식이다.

```json
{
  "success": false,
  "data": null,
  "message": "오류 안내 문구",
  "error_code": "ERROR_CODE"
}
```

### 성공 응답 형식

현재 dn Router의 성공 응답은 각 API의 `response_model` JSON을 그대로 반환한다.
dy API의 `success/data/message/error_code` 성공 형식과 다르므로, 프론트엔드는
dn API와 dy API의 성공 응답을 구분해서 처리해야 한다.

---

## 상태 확인

### `GET /`

| 항목 | 값 |
| --- | --- |
| 인증 | 불필요 |
| 성공 | `200 OK` |

```json
{
  "success": true,
  "data": { "service": "aio-01-p1-team5 API" },
  "message": "ok",
  "error_code": null
}
```

### `GET /health`

| 항목 | 값 |
| --- | --- |
| 인증 | 불필요 |
| 성공 | `200 OK` |

```json
{
  "success": true,
  "data": { "status": "healthy" },
  "message": "ok",
  "error_code": null
}
```

---

## 인증 API

### `POST /auth/signup` — 회원가입

| 항목 | 값 |
| --- | --- |
| 인증 | 불필요 |
| Content-Type | `application/json` |
| 성공 | `201 Created` |

요청:

```json
{
  "email": "user@example.com",
  "password": "TestPass1234!",
  "name": "홍길동"
}
```

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `email` | string | 올바른 이메일 형식 |
| `password` | string | 8~72자 |
| `name` | string | 1~50자 |

성공 응답:

```json
{
  "id": "0d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
  "email": "user@example.com",
  "name": "홍길동",
  "phone": null,
  "role": "USER",
  "profile_image_url": null,
  "created_at": "2026-08-08T12:00:00"
}
```

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 409 | `EMAIL_ALREADY_EXISTS` | 이미 가입한 이메일 |
| 422 | `VALIDATION_ERROR` | 요청값 형식 또는 길이 오류 |

### `POST /auth/signin` — 로그인

| 항목 | 값 |
| --- | --- |
| 인증 | 불필요 |
| Content-Type | `application/x-www-form-urlencoded` |
| 성공 | `200 OK` |

요청 form-data:

```text
email=user@example.com
password=TestPass1234!
```

> 필드명은 `username`이 아니라 반드시 `email`이다.

성공 응답:

```json
{
  "user": {
    "id": "0d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
    "email": "user@example.com",
    "name": "홍길동",
    "phone": null,
    "role": "USER",
    "profile_image_url": null,
    "created_at": "2026-08-08T12:00:00"
  },
  "session_token": "발급된_세션_토큰",
  "expires_at": "2026-08-08T13:00:00+00:00"
}
```

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 401 | `INVALID_CREDENTIALS` | 이메일이 없거나 비밀번호 불일치 |
| 422 | `VALIDATION_ERROR` | form-data 누락 |

### `POST /auth/signout` — 로그아웃

| 항목 | 값 |
| --- | --- |
| 인증 | 필요 |
| 성공 | `204 No Content` |

해당 세션 토큰을 `sessions` 테이블에서 삭제한다. 성공 시 response body는 없다.

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 토큰 누락 또는 유효하지 않은 토큰 |
| 401 | `SESSION_EXPIRED` | 만료된 세션 |

---

## 사용자 API

### `GET /users/me` — 내 정보 조회

| 항목 | 값 |
| --- | --- |
| 인증 | 필요 |
| 성공 | `200 OK` |

성공 응답은 회원가입의 사용자 응답과 같다.

### `PATCH /users/me` — 내 정보 수정

| 항목 | 값 |
| --- | --- |
| 인증 | 필요 |
| Content-Type | `application/json` |
| 성공 | `200 OK` |

수정할 필드만 보낸다.

```json
{
  "name": "수정된 이름",
  "phone": "010-1234-5678",
  "profile_image_url": "/static/uploads/profile.png"
}
```

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `name` | string | 1~50자, 선택 |
| `phone` | string/null | 최대 30자, 선택 |
| `profile_image_url` | string/null | 최대 500자, 선택 |

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 400 | `NO_UPDATE_FIELDS` | 수정 필드를 하나도 보내지 않음 |
| 401 | `UNAUTHORIZED`, `SESSION_EXPIRED` | 인증 실패 |
| 404 | `USER_NOT_FOUND` | 세션 사용자가 없음 |
| 422 | `VALIDATION_ERROR` | 입력값 오류 |

### `GET /users` — 사용자 목록 조회

| 항목 | 값 |
| --- | --- |
| 인증 | ADMIN 필요 |
| 성공 | `200 OK` |

Query parameter:

| 이름 | 기본값 | 규칙 |
| --- | --- | --- |
| `offset` | `0` | 0 이상 |
| `limit` | `20` | 1~100 |

성공 응답:

```json
{
  "items": [],
  "total": 0,
  "offset": 0,
  "limit": 20
}
```

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED`, `SESSION_EXPIRED` | 인증 실패 |
| 403 | `FORBIDDEN` | 일반 사용자의 관리자 기능 접근 |
| 422 | `VALIDATION_ERROR` | 페이지네이션 값 오류 |

### `PATCH /users/{user_id}/role` — 사용자 권한 변경

| 항목 | 값 |
| --- | --- |
| 인증 | ADMIN 필요 |
| Content-Type | `application/json` |
| 성공 | `200 OK` |

```json
{
  "role": "ADMIN"
}
```

`role`은 `USER` 또는 `ADMIN`만 허용한다. 성공 시 변경된 사용자 정보를 반환한다.

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED`, `SESSION_EXPIRED` | 인증 실패 |
| 403 | `FORBIDDEN` | 일반 사용자의 권한 변경 시도 |
| 404 | `USER_NOT_FOUND` | 대상 사용자가 없음 |
| 422 | `VALIDATION_ERROR` | UUID 또는 role 값 오류 |

---

## 챗봇 API

### `POST /chat/messages` — Gemini 메시지 전송

| 항목 | 값 |
| --- | --- |
| 인증 | 필요 |
| Content-Type | `application/json` |
| 성공 | `200 OK` |

첫 대화는 `conversation_id` 없이 요청한다.

```json
{
  "message": "인천에서 제주로 가는 항공권은 어떻게 검색하나요?"
}
```

같은 대화를 이어갈 때는 이전 응답의 `conversation_id`를 함께 보낸다.

```json
{
  "conversation_id": "0d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
  "message": "좌석은 언제 선택할 수 있나요?"
}
```

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `message` | string | 1~2,000자, 필수 |
| `conversation_id` | UUID | 선택 |

성공 응답:

```json
{
  "conversation_id": "0d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
  "user_message_id": "1d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
  "assistant_message_id": "2d9e6b56-1dd5-485a-a5c4-f174aef7e7f0",
  "answer": "항공편 검색 화면에서 출발지와 도착지를 입력해 주세요.",
  "created_at": "2026-08-08T12:00:00+00:00"
}
```

질문과 Gemini 답변은 모두 `chat_messages` 테이블에 같은 `conversation_id`로 저장된다.

| 실패 상태 | `error_code` | 설명 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED`, `SESSION_EXPIRED` | 인증 실패 |
| 429 | `GEMINI_RATE_LIMITED` | Gemini 호출 한도 초과 |
| 502 | `GEMINI_API_ERROR` | Gemini API 호출 실패 |
| 502 | `GEMINI_EMPTY_RESPONSE` | Gemini 응답이 비어 있음 |
| 422 | `VALIDATION_ERROR` | 메시지 또는 UUID 형식 오류 |

---

## 연동 체크리스트

1. 로그인 응답의 `session_token`을 사용자·관리자 API의 Bearer 토큰으로 사용한다.
2. Swagger의 **Authorize** 입력란에는 `Bearer` 접두사 없이 토큰 값만 넣는다.
3. HTTP 클라이언트(Postman, Streamlit `requests`)에서는 `Authorization: Bearer {token}` 헤더를 직접 넣는다.
4. dy의 예약·피드백·업로드 API는 성공 응답도 공통 wrapper를 사용하므로, dn API의 성공 응답과 다름을 주의한다.
