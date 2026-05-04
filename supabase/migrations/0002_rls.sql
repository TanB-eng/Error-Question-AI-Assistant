alter table public.users enable row level security;
alter table public.subjects enable row level security;
alter table public.mistakes enable row level security;
alter table public.notes enable row level security;
alter table public.tags enable row level security;
alter table public.mistake_tags enable row level security;
alter table public.note_tags enable row level security;
alter table public.ingest_sessions enable row level security;
alter table public.llm_calls enable row level security;

drop policy if exists users_select_own on public.users;
create policy users_select_own on public.users
  for select using (auth.uid() = id);

drop policy if exists users_update_own on public.users;
create policy users_update_own on public.users
  for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists subjects_read_authenticated on public.subjects;
create policy subjects_read_authenticated on public.subjects
  for select using (auth.role() = 'authenticated');

drop policy if exists mistakes_select_own on public.mistakes;
create policy mistakes_select_own on public.mistakes
  for select using (auth.uid() = user_id);

drop policy if exists mistakes_insert_own on public.mistakes;
create policy mistakes_insert_own on public.mistakes
  for insert with check (auth.uid() = user_id);

drop policy if exists mistakes_update_own on public.mistakes;
create policy mistakes_update_own on public.mistakes
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists notes_select_own on public.notes;
create policy notes_select_own on public.notes
  for select using (auth.uid() = user_id);

drop policy if exists notes_insert_own on public.notes;
create policy notes_insert_own on public.notes
  for insert with check (auth.uid() = user_id);

drop policy if exists notes_update_own on public.notes;
create policy notes_update_own on public.notes
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists tags_select_own on public.tags;
create policy tags_select_own on public.tags
  for select using (auth.uid() = user_id);

drop policy if exists tags_insert_own on public.tags;
create policy tags_insert_own on public.tags
  for insert with check (auth.uid() = user_id);

drop policy if exists tags_update_own on public.tags;
create policy tags_update_own on public.tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists mistake_tags_select_own on public.mistake_tags;
create policy mistake_tags_select_own on public.mistake_tags
  for select using (auth.uid() = user_id);

drop policy if exists mistake_tags_insert_own on public.mistake_tags;
create policy mistake_tags_insert_own on public.mistake_tags
  for insert with check (auth.uid() = user_id);

drop policy if exists mistake_tags_update_own on public.mistake_tags;
create policy mistake_tags_update_own on public.mistake_tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists note_tags_select_own on public.note_tags;
create policy note_tags_select_own on public.note_tags
  for select using (auth.uid() = user_id);

drop policy if exists note_tags_insert_own on public.note_tags;
create policy note_tags_insert_own on public.note_tags
  for insert with check (auth.uid() = user_id);

drop policy if exists note_tags_update_own on public.note_tags;
create policy note_tags_update_own on public.note_tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists ingest_sessions_select_own on public.ingest_sessions;
create policy ingest_sessions_select_own on public.ingest_sessions
  for select using (auth.uid() = user_id);

drop policy if exists ingest_sessions_insert_own on public.ingest_sessions;
create policy ingest_sessions_insert_own on public.ingest_sessions
  for insert with check (auth.uid() = user_id);

drop policy if exists ingest_sessions_update_own on public.ingest_sessions;
create policy ingest_sessions_update_own on public.ingest_sessions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists llm_calls_select_own on public.llm_calls;
create policy llm_calls_select_own on public.llm_calls
  for select using (auth.uid() = user_id);

drop policy if exists llm_calls_insert_own on public.llm_calls;
create policy llm_calls_insert_own on public.llm_calls
  for insert with check (auth.uid() = user_id);

drop policy if exists llm_calls_update_own on public.llm_calls;
create policy llm_calls_update_own on public.llm_calls
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
