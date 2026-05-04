create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  nickname text,
  avatar_url text
);

create table if not exists public.subjects (
  id smallint primary key,
  code text not null unique,
  name text not null unique,
  sort_order smallint not null
);

create table if not exists public.mistakes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  subject_id smallint not null references public.subjects(id) on delete restrict,
  source_type text not null check (source_type in ('photo', 'pdf')),
  object_key text not null,
  preview_object_key text,
  ocr_text text not null default '',
  question text not null default '',
  my_answer text not null default '',
  correct_answer text not null default '',
  analysis text not null default '',
  question_type text not null default '',
  difficulty smallint check (difficulty is null or difficulty between 1 and 5),
  error_cause text not null default '',
  status text not null default 'active' check (status in ('active', 'pending')),
  answer_status text not null default 'unreviewed'
    check (answer_status in ('unreviewed', 'corrected', 'pending')),
  annotation text not null default '',
  last_viewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  subject_id smallint not null references public.subjects(id) on delete restrict,
  source_type text not null check (source_type in ('photo', 'pdf')),
  object_key text not null,
  preview_object_key text,
  ocr_text text not null default '',
  content text not null default '',
  status text not null default 'active' check (status in ('active', 'pending')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists public.tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  subject_id smallint not null references public.subjects(id) on delete restrict,
  kind text not null check (kind in ('knowledge_point', 'question_type', 'error_cause')),
  name text not null,
  normalized_name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create unique index if not exists tags_user_subject_kind_normalized_active_uidx
  on public.tags (user_id, subject_id, kind, normalized_name)
  where deleted_at is null;

create table if not exists public.mistake_tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  mistake_id uuid not null references public.mistakes(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete restrict,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create unique index if not exists mistake_tags_active_uidx
  on public.mistake_tags (user_id, mistake_id, tag_id)
  where deleted_at is null;

create table if not exists public.note_tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  note_id uuid not null references public.notes(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete restrict,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create unique index if not exists note_tags_active_uidx
  on public.note_tags (user_id, note_id, tag_id)
  where deleted_at is null;

create table if not exists public.ingest_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  scene text not null check (scene in ('mistake', 'note')),
  source_type text not null check (source_type in ('photo', 'pdf')),
  subject_id smallint references public.subjects(id) on delete restrict,
  object_key text,
  mime_type text not null,
  status text not null default 'created'
    check (status in (
      'created',
      'uploaded',
      'ocr_done',
      'classified',
      'pending',
      'saved',
      'failed',
      'abandoned'
    )),
  ocr_text text not null default '',
  candidate_payload jsonb not null default '{}'::jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),
  deleted_at timestamptz
);

create table if not exists public.llm_calls (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  mistake_id uuid references public.mistakes(id) on delete set null,
  note_id uuid references public.notes(id) on delete set null,
  ingest_session_id uuid references public.ingest_sessions(id) on delete set null,
  prompt_name text not null,
  prompt_version text not null,
  model text not null,
  input_tokens integer not null default 0 check (input_tokens >= 0),
  output_tokens integer not null default 0 check (output_tokens >= 0),
  latency_ms integer not null check (latency_ms >= 0),
  schema_hit boolean not null,
  retry_count smallint not null default 0 check (retry_count >= 0),
  error_code text,
  created_at timestamptz not null default now()
);

create index if not exists mistakes_user_subject_active_idx
  on public.mistakes (user_id, subject_id, created_at desc)
  where deleted_at is null;

create index if not exists mistakes_today_review_idx
  on public.mistakes (user_id, created_at desc)
  where deleted_at is null and status = 'active';

create index if not exists notes_user_subject_active_idx
  on public.notes (user_id, subject_id, created_at desc)
  where deleted_at is null;

create index if not exists ingest_sessions_user_status_idx
  on public.ingest_sessions (user_id, status, updated_at desc)
  where deleted_at is null;

create index if not exists llm_calls_user_created_idx
  on public.llm_calls (user_id, created_at desc);

create or replace view public.active_mistakes as
  select * from public.mistakes
  where deleted_at is null;

create or replace view public.active_notes as
  select * from public.notes
  where deleted_at is null;

create or replace view public.active_tags as
  select * from public.tags
  where deleted_at is null;
