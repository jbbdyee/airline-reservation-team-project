-- 예약 생성·취소 원자성 보장 RPC
-- schema.sql 적용 후 Supabase SQL Editor에서 실행한다.
-- 공통 DB 스키마 소유자(dn) 검토 후 개발/운영 DB에 적용할 것.

begin;

create or replace function public.create_booking_atomic(
    p_user_id uuid,
    p_flight_id uuid,
    p_seat_id uuid,
    p_passenger_name text,
    p_booking_code text
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    v_seat public.seats%rowtype;
    v_flight public.flights%rowtype;
    v_booking public.bookings%rowtype;
    v_constraint text;
begin
    select * into v_seat
      from public.seats
     where id = p_seat_id
     for update;

    if not found then
        raise exception using errcode = 'P0001', message = 'SEAT_NOT_FOUND';
    end if;

    if v_seat.flight_id <> p_flight_id then
        raise exception using errcode = 'P0001', message = 'FLIGHT_SEAT_MISMATCH';
    end if;

    select * into v_flight
      from public.flights
     where id = p_flight_id;

    if not found then
        raise exception using errcode = 'P0001', message = 'FLIGHT_NOT_FOUND';
    end if;

    if v_flight.status not in ('SCHEDULED', 'DELAYED')
       or v_flight.departure_at <= timezone('utc', now()) then
        raise exception using errcode = 'P0001', message = 'FLIGHT_NOT_BOOKABLE';
    end if;

    if v_seat.status <> 'AVAILABLE'
       or exists (
           select 1
             from public.bookings
            where seat_id = p_seat_id
              and status = 'CONFIRMED'
       ) then
        raise exception using errcode = 'P0001', message = 'SEAT_ALREADY_BOOKED';
    end if;

    if nullif(btrim(p_passenger_name), '') is null then
        raise exception using errcode = 'P0001', message = 'INVALID_PASSENGER_NAME';
    end if;

    insert into public.bookings (
        booking_code,
        user_id,
        flight_id,
        seat_id,
        passenger_name,
        status,
        total_price
    ) values (
        p_booking_code,
        p_user_id,
        p_flight_id,
        p_seat_id,
        btrim(p_passenger_name),
        'CONFIRMED',
        v_seat.price
    )
    returning * into v_booking;

    update public.seats
       set status = 'BOOKED'
     where id = p_seat_id;

    insert into public.event_logs (
        event_type,
        resource_id,
        flight_id,
        booking_id,
        actor_user_id,
        payload
    ) values (
        'BOOKING_CHANGED',
        v_booking.id,
        v_booking.flight_id,
        v_booking.id,
        p_user_id,
        jsonb_build_object(
            'action', 'CREATED',
            'previous_status', null,
            'status', 'CONFIRMED',
            'seat_id', v_booking.seat_id
        )
    );

    return to_jsonb(v_booking);
exception
    when unique_violation then
        get stacked diagnostics v_constraint = constraint_name;
        if v_constraint = 'bookings_booking_code_key' then
            raise exception using errcode = 'P0001', message = 'BOOKING_CODE_CONFLICT';
        end if;
        raise exception using errcode = 'P0001', message = 'SEAT_ALREADY_BOOKED';
end;
$$;


create or replace function public.cancel_booking_atomic(
    p_booking_id uuid,
    p_user_id uuid,
    p_reason text default null
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    v_booking public.bookings%rowtype;
    v_flight public.flights%rowtype;
begin
    select * into v_booking
      from public.bookings
     where id = p_booking_id
     for update;

    if not found then
        raise exception using errcode = 'P0001', message = 'BOOKING_NOT_FOUND';
    end if;

    if v_booking.user_id <> p_user_id then
        raise exception using errcode = 'P0001', message = 'BOOKING_ACCESS_DENIED';
    end if;

    if v_booking.status = 'CANCELLED' then
        raise exception using errcode = 'P0001', message = 'BOOKING_ALREADY_CANCELLED';
    end if;

    select * into v_flight
      from public.flights
     where id = v_booking.flight_id;

    if v_flight.status = 'DEPARTED'
       or v_flight.departure_at <= timezone('utc', now()) then
        raise exception using errcode = 'P0001', message = 'BOOKING_NOT_CANCELLABLE';
    end if;

    perform 1
      from public.seats
     where id = v_booking.seat_id
     for update;

    update public.bookings
       set status = 'CANCELLED',
           cancelled_at = timezone('utc', now()),
           cancel_reason = nullif(btrim(p_reason), '')
     where id = v_booking.id
    returning * into v_booking;

    update public.seats
       set status = 'AVAILABLE'
     where id = v_booking.seat_id;

    insert into public.event_logs (
        event_type,
        resource_id,
        flight_id,
        booking_id,
        actor_user_id,
        payload
    ) values (
        'BOOKING_CHANGED',
        v_booking.id,
        v_booking.flight_id,
        v_booking.id,
        p_user_id,
        jsonb_build_object(
            'action', 'CANCELLED',
            'previous_status', 'CONFIRMED',
            'status', 'CANCELLED',
            'seat_id', v_booking.seat_id,
            'reason', nullif(btrim(p_reason), '')
        )
    );

    return to_jsonb(v_booking);
end;
$$;


create or replace function public.set_booking_status_atomic(
    p_booking_id uuid,
    p_status text,
    p_actor_user_id uuid
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
    v_booking public.bookings%rowtype;
    v_flight public.flights%rowtype;
    v_seat public.seats%rowtype;
    v_previous_status text;
begin
    if p_status not in ('CONFIRMED', 'CANCELLED') then
        raise exception using errcode = 'P0001', message = 'INVALID_BOOKING_STATUS';
    end if;

    select * into v_booking
      from public.bookings
     where id = p_booking_id
     for update;

    if not found then
        raise exception using errcode = 'P0001', message = 'BOOKING_NOT_FOUND';
    end if;

    if v_booking.status = p_status then
        return to_jsonb(v_booking);
    end if;

    select * into v_seat
      from public.seats
     where id = v_booking.seat_id
     for update;

    if p_status = 'CONFIRMED' then
        select * into v_flight
          from public.flights
         where id = v_booking.flight_id;

        if v_flight.status not in ('SCHEDULED', 'DELAYED')
           or v_flight.departure_at <= timezone('utc', now()) then
            raise exception using errcode = 'P0001', message = 'FLIGHT_NOT_BOOKABLE';
        end if;

        if v_seat.status <> 'AVAILABLE'
           or exists (
               select 1
                 from public.bookings
                where seat_id = v_booking.seat_id
                  and status = 'CONFIRMED'
                  and id <> v_booking.id
           ) then
            raise exception using errcode = 'P0001', message = 'SEAT_ALREADY_BOOKED';
        end if;
    end if;

    v_previous_status := v_booking.status;
    update public.bookings
       set status = p_status,
           cancelled_at = case
               when p_status = 'CANCELLED' then timezone('utc', now())
               else null
           end,
           cancel_reason = case
               when p_status = 'CANCELLED' then cancel_reason
               else null
           end
     where id = v_booking.id
    returning * into v_booking;

    update public.seats
       set status = case
           when p_status = 'CONFIRMED' then 'BOOKED'
           else 'AVAILABLE'
       end
     where id = v_booking.seat_id;

    insert into public.event_logs (
        event_type,
        resource_id,
        flight_id,
        booking_id,
        actor_user_id,
        payload
    ) values (
        'BOOKING_CHANGED',
        v_booking.id,
        v_booking.flight_id,
        v_booking.id,
        p_actor_user_id,
        jsonb_build_object(
            'action', 'ADMIN_STATUS_CHANGED',
            'previous_status', v_previous_status,
            'status', p_status,
            'seat_id', v_booking.seat_id
        )
    );

    return to_jsonb(v_booking);
end;
$$;

commit;
