-- =========================================================
-- aio-01-p1-team5 : 항공권 예약 프로그램 DB 스키마
-- 근거: plan.md 6-2 데이터베이스 명세, 예약 무결성 기준
-- 대상: PostgreSQL (Supabase)
--
-- [스키마 변경 규칙]
-- create table if not exists는 "테이블이 아직 없을 때만" 생성한다.
-- 이미 생성된 테이블의 컬럼을 추가/수정해야 하면 이 파일을 고쳐서 재실행해도
-- 반영되지 않는다. 반드시 별도 마이그레이션(alter table ...)을 작성해서 적용한다.
-- 예: alter table public.flights add column if not exists gate text;
--
-- [UTC 저장 규칙]
-- 모든 timestamp 컬럼은 UTC 기준으로 저장하고, 화면에서 KST로 변환해 보여준다.
-- - now() 기반 기본값은 timezone('utc', now())로 명시해 세션 타임존 설정과
--   무관하게 항상 UTC로 저장되도록 한다.
-- - departure_at/arrival_at/cancelled_at/reviewed_at처럼 애플리케이션이 직접
--   값을 넣는 컬럼은 DB가 UTC 여부를 강제할 수 없다. 백엔드에서 KST 입력을
--   반드시 UTC로 변환한 뒤 저장하도록 규칙을 지킨다.
-- - 더 안전하게 가려면 timestamp 대신 timestamptz로 바꾸는 것을 권장한다.
--   (timestamptz는 항상 UTC로 내부 저장되어 앱 실수에 덜 취약하다.
--   단, 컬럼 타입 변경은 공통 스키마 변경이라 팀 공유 후 결정할 것.)
-- =========================================================

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------
-- 1. users
-- ---------------------------------------------------------
create table if not exists public.users (
    id                  uuid primary key default gen_random_uuid(),
    email               text not null unique,
    password_hash       text not null,
    name                text not null,
    phone               text,
    role                text not null default 'USER'
                        check (role in ('USER', 'ADMIN')),
    profile_image_url   text,
    created_at          timestamp not null default timezone('utc', now())
);

-- ---------------------------------------------------------
-- 2. airports
-- ---------------------------------------------------------
create table if not exists public.airports (
    id          uuid primary key default gen_random_uuid(),
    iata_code   varchar(3) not null unique,
    name        text not null,
    city        text not null,
    country     text not null
);

-- ---------------------------------------------------------
-- 3. chat_messages
-- ---------------------------------------------------------
create table if not exists public.chat_messages (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null references public.users (id),
    conversation_id     uuid not null,
    role                text not null
                        check (role in ('USER', 'ASSISTANT')),
    content             text not null,
    created_at          timestamp not null default timezone('utc', now())
);

create index if not exists ix_chat_messages_conversation_id
    on public.chat_messages (conversation_id);

-- ---------------------------------------------------------
-- 4. flights
-- 출발/도착 공항 동일 방지, 도착 시각이 출발 시각보다 빨라지는 것 방지,
-- 기본 운임 음수 방지
-- ---------------------------------------------------------
create table if not exists public.flights (
    id                          uuid primary key default gen_random_uuid(),
    flight_number               text not null,
    origin_airport_id           uuid not null references public.airports (id),
    destination_airport_id      uuid not null references public.airports (id),
    departure_at                timestamp not null,
    arrival_at                  timestamp not null,
    status                      text not null default 'SCHEDULED'
                                check (status in ('SCHEDULED', 'DELAYED', 'CANCELLED', 'DEPARTED')),
    base_price                  integer not null
                                check (base_price > 0),
    created_at                  timestamp not null default timezone('utc', now()),
    check (origin_airport_id <> destination_airport_id),
    check (arrival_at > departure_at)
);

create index if not exists ix_flights_origin_destination_departure
    on public.flights (origin_airport_id, destination_airport_id, departure_at);

-- ---------------------------------------------------------
-- 5. seats
-- 좌석 가격 음수 방지
-- ---------------------------------------------------------
create table if not exists public.seats (
    id              uuid primary key default gen_random_uuid(),
    flight_id       uuid not null references public.flights (id),
    seat_number     text not null,
    cabin_class     text not null
                    check (cabin_class in ('ECONOMY', 'BUSINESS')),
    price           integer not null
                    check (price > 0),
    status          text not null default 'AVAILABLE'
                    check (status in ('AVAILABLE', 'HELD', 'BOOKED')),
    unique (flight_id, seat_number),
    unique (id, flight_id)
);

-- ---------------------------------------------------------
-- 6. bookings
-- 예약 금액 음수 방지
-- ---------------------------------------------------------
create table if not exists public.bookings (
    id                  uuid primary key default gen_random_uuid(),
    booking_code        text not null unique,
    user_id             uuid not null references public.users (id),
    flight_id           uuid not null references public.flights (id),
    seat_id             uuid not null references public.seats (id),
    passenger_name      text not null,
    status              text not null default 'CONFIRMED'
                        check (status in ('CONFIRMED', 'CANCELLED')),
    total_price         integer not null
                        check (total_price > 0),
    created_at          timestamp not null default timezone('utc', now()),
    cancelled_at        timestamp,
    cancel_reason       text,
    foreign key (seat_id, flight_id) references public.seats (id, flight_id)
);

create index if not exists ix_bookings_user_id
    on public.bookings (user_id);

create unique index if not exists ux_bookings_active_seat
    on public.bookings (seat_id)
    where status = 'CONFIRMED';

-- ---------------------------------------------------------
-- 7. event_logs
-- ---------------------------------------------------------
create table if not exists public.event_logs (
    id              bigserial primary key,
    event_type      text not null
                    check (event_type in ('FLIGHT_STATUS_CHANGED', 'SEAT_CHANGED', 'BOOKING_CHANGED')),
    resource_id     uuid not null,
    flight_id       uuid references public.flights (id),
    booking_id      uuid references public.bookings (id),
    actor_user_id   uuid references public.users (id),
    payload         jsonb not null,
    created_at      timestamp not null default timezone('utc', now())
);

create index if not exists ix_event_logs_event_type_created_at
    on public.event_logs (event_type, created_at);
create index if not exists ix_event_logs_flight_id
    on public.event_logs (flight_id);
create index if not exists ix_event_logs_booking_id
    on public.event_logs (booking_id);

-- ---------------------------------------------------------
-- 8. feedbacks
-- category = 'CHATBOT'이면 conversation_id, assistant_message_id 둘 다 필수
-- (plan.md 6-1 "챗봇 상담 평가 등록" API가 두 값을 모두 받도록 정의되어 있음)
-- comment 컬럼명은 API 스펙(챗봇 평가 등록 요청값: rating, comment)과 통일
--
-- 주의: 이미 feedbacks 테이블이 존재하는 DB에서는 이 파일을 재실행해도
-- 컬럼명이 자동으로 바뀌지 않는다. 기존 DB에는 아래를 직접 실행할 것.
--   alter table public.feedbacks rename column content to comment;
-- ---------------------------------------------------------
create table if not exists public.feedbacks (
    id                      uuid primary key default gen_random_uuid(),
    user_id                 uuid not null references public.users (id),
    rating                  integer not null
                            check (rating between 1 and 5),
    category                text not null
                            check (category in ('SERVICE', 'SEARCH', 'BOOKING', 'CHATBOT', 'ETC')),
    comment                 text
                            check (comment is null or char_length(comment) <= 1000),
    conversation_id         uuid,
    assistant_message_id    uuid references public.chat_messages (id),
    issue_type              text
                            check (issue_type is null or issue_type in ('INACCURATE', 'MISUNDERSTOOD', 'INSUFFICIENT', 'SLOW', 'ETC')),
    improvement_note        text,
    reviewed_by             uuid references public.users (id),
    reviewed_at             timestamp,
    created_at              timestamp not null default timezone('utc', now()),
    unique (user_id, conversation_id),
    check (
        category <> 'CHATBOT'
        or (conversation_id is not null and assistant_message_id is not null)
    )
);

create index if not exists ix_feedbacks_rating_category
    on public.feedbacks (rating, category);
create index if not exists ix_feedbacks_created_at
    on public.feedbacks (created_at);

create table if not exists public.sessions (
    id           uuid primary key default gen_random_uuid(),
    token        text not null unique,
    user_id      uuid not null references public.users (id),
    expires_at   timestamp not null,
    created_at   timestamp not null default timezone('utc', now())
);

create index if not exists ix_sessions_user_id on public.sessions (user_id);
create index if not exists ix_sessions_expires_at on public.sessions (expires_at);
