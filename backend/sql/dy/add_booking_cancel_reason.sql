alter table public.bookings
    add column if not exists cancel_reason text;

-- 기존 취소 건은 가장 최근 BOOKING_CHANGED 이벤트의 사유로 복원합니다.
update public.bookings as booking
   set cancel_reason = event.reason
  from (
      select distinct on (booking_id)
             booking_id,
             nullif(btrim(payload ->> 'reason'), '') as reason
        from public.event_logs
       where event_type = 'BOOKING_CHANGED'
         and booking_id is not null
         and payload ->> 'action' = 'CANCELLED'
       order by booking_id, created_at desc
  ) as event
 where booking.id = event.booking_id
   and booking.cancel_reason is null
   and event.reason is not null;
