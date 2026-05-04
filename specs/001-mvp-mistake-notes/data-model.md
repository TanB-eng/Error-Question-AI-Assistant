# Data Model: 错题与笔记智能辅导 MVP

**Target migration**: `supabase/migrations/0001_init.sql`  
**Database**: Supabase Postgres  
**Security model**: all user-owned business tables enable RLS with `auth.uid() = user_id`

## Entity Overview

| Entity | Table | Notes |
|---|---|---|
| User profile | `users` | mirrors Supabase Auth user; service_role may create row at registration |
| Subject dictionary | `subjects` | fixed dictionary, no user ownership |
| Mistake | `mistakes` | user-owned, soft delete, review state |
| Note | `notes` | user-owned, soft delete |
| Tag | `tags` | user-owned; unique normalized name per subject/kind |
| Mistake tags | `mistake_tags` | user-owned M:N join |
| Note tags | `note_tags` | user-owned M:N join |
| Ingest session | `ingest_sessions` | user-owned recovery state for interrupted upload/review |
| LLM audit | `llm_calls` | user-owned audit of DeepSeek calls |

## State Rules

### Mistake status

| Status | Meaning |
|---|---|
| `active` | reviewed and visible in normal lists |
| `pending` | OCR/LLM failed or tags not completed; visible in “待整理” |
| `trashed` | represented by `deleted_at is not null`, not a separate stored status |

### Ingest session status

| Status | Meaning |
|---|---|
| `created` | signed upload URL issued, file may not be uploaded yet |
| `uploaded` | storage object uploaded |
| `ocr_done` | OCR result available |
| `classified` | LLM candidate available |
| `pending` | degraded branch, user can manually complete |
| `saved` | user confirmed and final row created |
| `failed` | unrecoverable user-visible failure |
| `abandoned` | user discarded session |

## Table Details

### `users`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK, references `auth.users(id)` |
| `created_at` | timestamptz | not null default `now()` |
| `updated_at` | timestamptz | not null default `now()` |
| `deleted_at` | timestamptz | nullable |
| `nickname` | text | nullable |
| `avatar_url` | text | nullable |

RLS: users can read/update only their own profile. WeChat openid is not stored here to avoid logging or accidental exposure; if needed, store a non-reversible hash in a separate auth mapping controlled by admin-only code.

### `subjects`

| Field | Type | Constraints |
|---|---|---|
| `id` | smallint | PK |
| `code` | text | unique, not null |
| `name` | text | unique, not null |
| `sort_order` | smallint | not null |

Dictionary table, readable by authenticated users.

### `mistakes`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `subject_id` | smallint | not null references `subjects(id)` |
| `source_type` | text | `photo` or `pdf` |
| `object_key` | text | not null, private storage object key |
| `preview_object_key` | text | nullable |
| `ocr_text` | text | not null default empty |
| `question` | text | not null default empty |
| `my_answer` | text | not null default empty |
| `correct_answer` | text | not null default empty |
| `analysis` | text | not null default empty |
| `question_type` | text | not null default empty |
| `difficulty` | smallint | nullable, 1-5 |
| `error_cause` | text | not null default empty |
| `status` | text | `active` or `pending` |
| `answer_status` | text | `unreviewed`, `corrected`, `pending` |
| `annotation` | text | not null default empty |
| `last_viewed_at` | timestamptz | nullable |
| `created_at` | timestamptz | not null default `now()` |
| `updated_at` | timestamptz | not null default `now()` |
| `deleted_at` | timestamptz | nullable |

### `notes`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `subject_id` | smallint | not null references `subjects(id)` |
| `source_type` | text | `photo` or `pdf` |
| `object_key` | text | not null |
| `preview_object_key` | text | nullable |
| `ocr_text` | text | not null default empty |
| `content` | text | not null default empty |
| `status` | text | `active` or `pending` |
| `created_at` | timestamptz | not null default `now()` |
| `updated_at` | timestamptz | not null default `now()` |
| `deleted_at` | timestamptz | nullable |

### `tags`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `subject_id` | smallint | not null references `subjects(id)` |
| `kind` | text | `knowledge_point`, `question_type`, `error_cause` |
| `name` | text | user-facing name, not null |
| `normalized_name` | text | normalized unique key, not null |
| `created_at` | timestamptz | not null default `now()` |
| `updated_at` | timestamptz | not null default `now()` |
| `deleted_at` | timestamptz | nullable |

Unique index: `(user_id, subject_id, kind, normalized_name)` where `deleted_at is null`.

### `mistake_tags`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `mistake_id` | uuid | not null references `mistakes(id)` on delete cascade |
| `tag_id` | uuid | not null references `tags(id)` on delete restrict |
| `created_at` | timestamptz | not null default `now()` |
| `deleted_at` | timestamptz | nullable |

Unique active link: `(user_id, mistake_id, tag_id)` where `deleted_at is null`.

### `note_tags`

Same structure as `mistake_tags`, linking notes to tags.

### `ingest_sessions`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `scene` | text | `mistake` or `note` |
| `source_type` | text | `photo` or `pdf` |
| `subject_id` | smallint | nullable until chosen, but upload flow requires it |
| `object_key` | text | nullable until signed/uploaded |
| `mime_type` | text | not null |
| `status` | text | session state |
| `ocr_text` | text | not null default empty |
| `candidate_payload` | jsonb | not null default `{}` |
| `error_code` | text | nullable |
| `created_at` | timestamptz | not null default `now()` |
| `updated_at` | timestamptz | not null default `now()` |
| `expires_at` | timestamptz | not null default `now() + interval '7 days'` |
| `deleted_at` | timestamptz | nullable |

### `llm_calls`

| Field | Type | Constraints |
|---|---|---|
| `id` | uuid | PK default `gen_random_uuid()` |
| `user_id` | uuid | not null references `users(id)` |
| `mistake_id` | uuid | nullable references `mistakes(id)` |
| `note_id` | uuid | nullable references `notes(id)` |
| `ingest_session_id` | uuid | nullable references `ingest_sessions(id)` |
| `prompt_name` | text | not null |
| `prompt_version` | text | not null |
| `model` | text | not null |
| `input_tokens` | integer | not null default 0 |
| `output_tokens` | integer | not null default 0 |
| `latency_ms` | integer | not null |
| `schema_hit` | boolean | not null |
| `retry_count` | smallint | not null default 0 |
| `error_code` | text | nullable |
| `created_at` | timestamptz | not null default `now()` |

No raw prompt text, raw OCR text, images, openid, or phone number should be stored in this table.

## Query Views

Views provide default active filtering for application queries. RLS still applies on the underlying tables.

- `active_mistakes`: `mistakes where deleted_at is null and status in ('active', 'pending')`
- `active_notes`: `notes where deleted_at is null and status in ('active', 'pending')`
- `active_tags`: `tags where deleted_at is null`

## Migration DDL

```sql
create extension if not exists pgcrypto;

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  nickname text,
  avatar_url text
);

create table public.subjects (
  id smallint primary key,
  code text not null unique,
  name text not null unique,
  sort_order smallint not null
);

insert into public.subjects (id, code, name, sort_order) values
  (1, 'math', '数学', 1),
  (2, 'physics', '物理', 2),
  (3, 'chemistry', '化学', 3),
  (4, 'biology', '生物', 4),
  (5, 'chinese', '语文', 5),
  (6, 'english', '英语', 6),
  (7, 'history', '历史', 7),
  (8, 'geography', '地理', 8),
  (9, 'politics', '政治', 9),
  (10, 'specialized', '专业课', 10);

create table public.mistakes (
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
  answer_status text not null default 'unreviewed' check (answer_status in ('unreviewed', 'corrected', 'pending')),
  annotation text not null default '',
  last_viewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table public.notes (
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

create table public.tags (
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

create unique index tags_user_subject_kind_normalized_active_uidx
  on public.tags (user_id, subject_id, kind, normalized_name)
  where deleted_at is null;

create table public.mistake_tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  mistake_id uuid not null references public.mistakes(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete restrict,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create unique index mistake_tags_active_uidx
  on public.mistake_tags (user_id, mistake_id, tag_id)
  where deleted_at is null;

create table public.note_tags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  note_id uuid not null references public.notes(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete restrict,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create unique index note_tags_active_uidx
  on public.note_tags (user_id, note_id, tag_id)
  where deleted_at is null;

create table public.ingest_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete restrict,
  scene text not null check (scene in ('mistake', 'note')),
  source_type text not null check (source_type in ('photo', 'pdf')),
  subject_id smallint references public.subjects(id) on delete restrict,
  object_key text,
  mime_type text not null,
  status text not null default 'created' check (status in ('created', 'uploaded', 'ocr_done', 'classified', 'pending', 'saved', 'failed', 'abandoned')),
  ocr_text text not null default '',
  candidate_payload jsonb not null default '{}'::jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),
  deleted_at timestamptz
);

create table public.llm_calls (
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

create index mistakes_user_subject_active_idx
  on public.mistakes (user_id, subject_id, created_at desc)
  where deleted_at is null;

create index mistakes_today_review_idx
  on public.mistakes (user_id, created_at desc)
  where deleted_at is null and status = 'active';

create index notes_user_subject_active_idx
  on public.notes (user_id, subject_id, created_at desc)
  where deleted_at is null;

create index ingest_sessions_user_status_idx
  on public.ingest_sessions (user_id, status, updated_at desc)
  where deleted_at is null;

create index llm_calls_user_created_idx
  on public.llm_calls (user_id, created_at desc);

create view public.active_mistakes as
  select * from public.mistakes
  where deleted_at is null;

create view public.active_notes as
  select * from public.notes
  where deleted_at is null;

create view public.active_tags as
  select * from public.tags
  where deleted_at is null;
```

## RLS Policies

```sql
alter table public.users enable row level security;
alter table public.subjects enable row level security;
alter table public.mistakes enable row level security;
alter table public.notes enable row level security;
alter table public.tags enable row level security;
alter table public.mistake_tags enable row level security;
alter table public.note_tags enable row level security;
alter table public.ingest_sessions enable row level security;
alter table public.llm_calls enable row level security;

create policy users_select_own on public.users
  for select using (auth.uid() = id);
create policy users_update_own on public.users
  for update using (auth.uid() = id) with check (auth.uid() = id);

create policy subjects_read_authenticated on public.subjects
  for select using (auth.role() = 'authenticated');

create policy mistakes_select_own on public.mistakes
  for select using (auth.uid() = user_id);
create policy mistakes_insert_own on public.mistakes
  for insert with check (auth.uid() = user_id);
create policy mistakes_update_own on public.mistakes
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy notes_select_own on public.notes
  for select using (auth.uid() = user_id);
create policy notes_insert_own on public.notes
  for insert with check (auth.uid() = user_id);
create policy notes_update_own on public.notes
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy tags_select_own on public.tags
  for select using (auth.uid() = user_id);
create policy tags_insert_own on public.tags
  for insert with check (auth.uid() = user_id);
create policy tags_update_own on public.tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy mistake_tags_select_own on public.mistake_tags
  for select using (auth.uid() = user_id);
create policy mistake_tags_insert_own on public.mistake_tags
  for insert with check (auth.uid() = user_id);
create policy mistake_tags_update_own on public.mistake_tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy note_tags_select_own on public.note_tags
  for select using (auth.uid() = user_id);
create policy note_tags_insert_own on public.note_tags
  for insert with check (auth.uid() = user_id);
create policy note_tags_update_own on public.note_tags
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy ingest_sessions_select_own on public.ingest_sessions
  for select using (auth.uid() = user_id);
create policy ingest_sessions_insert_own on public.ingest_sessions
  for insert with check (auth.uid() = user_id);
create policy ingest_sessions_update_own on public.ingest_sessions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy llm_calls_select_own on public.llm_calls
  for select using (auth.uid() = user_id);
create policy llm_calls_insert_own on public.llm_calls
  for insert with check (auth.uid() = user_id);
```

## Storage Layout

Private bucket: `user-files`

Object key pattern:

```text
users/{user_id}/mistakes/{yyyy}/{mm}/{uuid}.{ext}
users/{user_id}/notes/{yyyy}/{mm}/{uuid}.{ext}
users/{user_id}/previews/{yyyy}/{mm}/{uuid}.jpg
```

The backend signs upload URLs. The frontend uploads directly to Supabase Storage. Reads require authenticated API mediation or short-lived signed read URLs generated for the owner only.
