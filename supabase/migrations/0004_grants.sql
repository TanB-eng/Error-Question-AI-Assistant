grant usage on schema public to authenticated, service_role;

grant select on public.subjects to authenticated;
grant select, insert, update, delete on public.subjects to service_role;

grant select on public.users to authenticated;
grant select, insert, update on public.users to service_role;

grant select, insert, update on public.mistakes to authenticated;
grant select, insert, update, delete on public.mistakes to service_role;

grant select, insert, update on public.notes to authenticated;
grant select, insert, update, delete on public.notes to service_role;

grant select, insert, update on public.tags to authenticated;
grant select, insert, update, delete on public.tags to service_role;

grant select, insert, update on public.mistake_tags to authenticated;
grant select, insert, update, delete on public.mistake_tags to service_role;

grant select, insert, update on public.note_tags to authenticated;
grant select, insert, update, delete on public.note_tags to service_role;

grant select, insert, update on public.ingest_sessions to authenticated;
grant select, insert, update, delete on public.ingest_sessions to service_role;

grant select, insert on public.llm_calls to authenticated;
grant select, insert, update, delete on public.llm_calls to service_role;

grant select on public.active_mistakes to authenticated;
grant select on public.active_notes to authenticated;
grant select on public.active_tags to authenticated;
grant select on public.active_mistakes to service_role;
grant select on public.active_notes to service_role;
grant select on public.active_tags to service_role;
