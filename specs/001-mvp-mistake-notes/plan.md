# Implementation Plan: 错题与笔记智能辅导 MVP

**Branch**: `001-mvp-mistake-notes`  
**Spec**: `specs/001-mvp-mistake-notes/spec.md`  
**Constitution**: `.specify/memory/constitution.md` v1.0.0  
**Date**: 2026-05-04

## Summary

第一期 MVP 交付微信小程序 + FastAPI + Supabase 的错题与笔记录入闭环：
微信登录、私有文件上传、OCR、DeepSeek 文本分类、用户校对、落库、按标签浏览、
软删除恢复、今日待复习占位列表。

本计划严格遵守宪法约束：小程序使用微信原生，后端使用 Python 3.11+ / FastAPI /
Pydantic v2 / uv，数据与鉴权使用 Supabase，LLM 使用 DeepSeek chat completions，
OCR 本期默认腾讯云 OCR，并通过抽象接口保留切换能力。

## Technical Context

| Area | Decision |
|---|---|
| Frontend | 微信小程序原生 WXML / WXSS / JS |
| Backend | Python 3.11+ / FastAPI / Pydantic v2 |
| Package Management | uv |
| Data/Auth/Storage | Supabase Postgres + Auth + private Storage |
| LLM | DeepSeek chat completions, text only, via `services/llm/deepseek.py` |
| OCR | 腾讯云 OCR default, behind `core/ocr_client.py` abstraction |
| Tests | pytest + httpx + respx; frontend logic tests with jest/minimal snapshots |
| Static Checks | ruff + mypy strict |
| CI | GitHub Actions: ruff, mypy strict, pytest all green before merge |

## Constitution Check

| Gate | Status | Evidence |
|---|---|---|
| Locked stack | Pass | Uses native WeChat Mini Program, FastAPI, Supabase, DeepSeek, uv |
| RLS on business tables | Pass | `data-model.md` enables RLS and `auth.uid() = user_id` policies |
| No service_role for user queries | Pass | service_role only for auth bootstrap/user row creation and migrations |
| User JWT for business requests | Pass | all protected API paths require Bearer JWT |
| Signed URL uploads | Pass | `/uploads/sign` returns private Supabase Storage object key and signed PUT URL |
| Route/service separation | Pass | routes call services; services call Supabase/OCR/LLM clients |
| Pydantic request/response models | Pass | contracts map to schemas under `backend/app/schemas/` |
| LLM JSON + schema validation | Pass | `ClassifyResult` validates DeepSeek JSON; retry once; fallback to pending |
| Prompt files under services/prompts | Pass | `classify_mistake_v1.md`, `classify_note_v1.md` planned |
| LLM audit | Pass | `llm_calls` records prompt version, tokens, latency, schema hit |
| User confirmation before final save | Pass | `/mistakes/ingest` returns candidates only; `/mistakes` persists after review |
| Soft delete | Pass | `deleted_at` on user data tables and 7-day restore flow |
| Quality gates | Pass | required tests listed below; CI blocks merge |

No constitution violations are introduced by this plan.

## Repository Layout

```text
repo-root/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── settings.py
│   │   │   ├── supabase.py
│   │   │   ├── deepseek.py
│   │   │   └── ocr_client.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── uploads.py
│   │   │   ├── mistakes.py
│   │   │   ├── notes.py
│   │   │   ├── tags.py
│   │   │   ├── subjects.py
│   │   │   └── today_review.py
│   │   ├── services/
│   │   │   ├── prompts/
│   │   │   │   ├── classify_mistake_v1.md
│   │   │   │   └── classify_note_v1.md
│   │   │   ├── ocr.py
│   │   │   ├── classifier.py
│   │   │   ├── ingestion.py
│   │   │   ├── tag_normalizer.py
│   │   │   ├── mistakes.py
│   │   │   ├── notes.py
│   │   │   └── auth.py
│   │   ├── schemas/
│   │   ├── deps.py
│   │   └── errors.py
│   ├── tests/
│   └── pyproject.toml
├── supabase/
│   └── migrations/
│       └── 0001_init.sql
├── frontend/
│   ├── pages/
│   │   ├── login/
│   │   ├── home/
│   │   ├── capture/
│   │   ├── review-form/
│   │   ├── list/
│   │   ├── detail/
│   │   ├── notes/
│   │   ├── today-review/
│   │   └── settings/
│   ├── components/
│   │   ├── tag-picker/
│   │   ├── mistake-card/
│   │   └── empty-state/
│   ├── services/
│   ├── utils/request.js
│   └── app.json
└── docs/
```

Routes must not access Supabase, OCR, or DeepSeek directly. They parse request data,
inject `current_user`, and call service functions.

## Key Flows

### A. Photo Mistake Ingestion

```mermaid
sequenceDiagram
    participant MP as Frontend
    participant API as FastAPI
    participant ST as Supabase Storage
    participant OCR as Tencent OCR
    participant LLM as DeepSeek
    participant DB as Supabase Postgres

    MP->>MP: User selects subject, wx.chooseMedia
    MP->>API: POST /uploads/sign (scene=mistake, mime_type=image/jpeg)
    API->>ST: Create signed PUT URL for private object
    API-->>MP: signed_url + object_key
    MP->>ST: wx.uploadFile direct upload
    MP->>API: POST /mistakes/ingest (object_key, source_type=photo, subject_hint)
    API->>ST: Fetch private object as user
    API->>OCR: OCR image text
    API->>LLM: Classify OCR text, JSON required
    LLM-->>API: JSON or invalid output
    API->>API: Pydantic ClassifyResult validation; retry once on failure
    API->>DB: Insert llm_calls audit row
    alt schema valid
        API-->>MP: status=ready + structured candidate
        MP->>MP: User edits review-form
        MP->>API: POST /mistakes final reviewed fields
        API->>DB: Insert mistake; normalize/upsert tags; insert mistake_tags
    else schema invalid twice
        API-->>MP: status=pending + OCR text + empty tags
        MP->>MP: User fills manually or saves pending
    end
```

### B. PDF Mistake Import

1. User selects subject before upload.
2. Frontend accepts only `pdf`, max 10MB and max 20 pages.
3. `/uploads/sign` returns signed private Storage URL and `object_key`.
4. Frontend uploads directly to Supabase Storage.
5. `/mistakes/ingest` pulls the PDF, OCR extracts text and page layout.
6. `ingestion.py` performs question segmentation after OCR.
7. API returns independent candidates with page number, text, optional crop/preview key.
8. User checks only the wrong questions.
9. Each checked candidate enters the same review form shape as photo mistakes.
10. `/mistakes` persists reviewed rows and normalizes tags.

### C. Note Ingestion

Notes reuse upload/session/OCR mechanics but call a note classifier prompt and return only
subject + knowledge point tags + organized content. Notes do not require `difficulty`,
`question_type`, or `error_cause`.

### D. Label Normalization Algorithm

1. Basic normalization:
   - trim leading/trailing whitespace
   - remove internal spaces around Chinese text
   - convert full-width ASCII to half-width
   - normalize Chinese parentheses to `()`
   - remove trailing punctuation
   - lowercase Latin tokens
2. Synonym consolidation:
   - produce `normalized_name` from rules and a small per-subject synonym map
   - lookup `(user_id, subject_id, kind, normalized_name)`
   - reuse existing tag on hit
   - create new tag on miss
3. Persistence:
   - `tags` has unique index `(user_id, subject_id, kind, normalized_name)`
   - `mistake_tags` and `note_tags` store many-to-many links
4. Explicit non-goal:
   - no vector similarity or embedding search in MVP; keep as future extension.

## Backend Design

- `core/settings.py`: Pydantic Settings, all secrets from environment.
- `core/supabase.py`: user-JWT PostgREST client factory and limited admin client factory.
- `core/deepseek.py`: HTTP client with 30s timeout, one retry, structured errors.
- `core/ocr_client.py`: abstract `OCRClient` plus Tencent implementation.
- `services/ocr.py`: file-type dispatch, PDF page extraction, question segmentation handoff.
- `services/classifier.py`: prompt loading, DeepSeek call, schema validation, retry, audit.
- `services/ingestion.py`: orchestrates upload object fetch, OCR, classification, candidates.
- `services/tag_normalizer.py`: normalization, synonym map, upsert, link table writes.
- `services/mistakes.py` and `services/notes.py`: CRUD, soft delete, restore, list filters.
- `api/*`: request parsing, auth dependency injection, response models only.
- `errors.py`: maps internal errors to stable API error codes.

## Frontend Design

- `utils/request.js`: injects Bearer JWT, handles 401 by refreshing once, retries original request.
- `services/*.js`: typed-ish API wrappers; pages do not call raw URLs directly.
- `pages/login`: calls `wx.login`, then `/auth/wx-login`.
- `pages/home`: subject entry, today-review entry, capture shortcuts.
- `pages/capture`: subject-first upload flow; validates jpg/png/pdf, 5MB image, 10MB/20-page PDF.
- `pages/review-form`: central review and correction page for mistake/note candidates.
- `pages/list`: subject/tag/status filtered lists.
- `pages/detail`: full image/text/tags/edit/delete.
- `pages/today-review`: simple list and empty state.
- `pages/settings`: includes “回收站”.

## Error Handling Strategy

| Condition | User-visible behavior | API error/status |
|---|---|---|
| Missing JWT | redirect/login prompt | `AUTH_REQUIRED` / 401 |
| Expired access token | refresh once then retry | `TOKEN_EXPIRED` / 401 if refresh fails |
| Unsupported upload format | prompt supported formats | `UPLOAD_UNSUPPORTED_TYPE` / 400 |
| File too large/page over limit | prompt split upload | `UPLOAD_LIMIT_EXCEEDED` / 400 |
| OCR timeout/failure | allow manual save | candidate `status=pending_ocr` |
| DeepSeek invalid JSON twice | saveable pending branch | candidate `status=pending_classification` |
| Cross-user access | empty/forbidden, no data leak | `NOT_FOUND` or `FORBIDDEN` |
| Restore after 7 days | cannot restore | `RESTORE_WINDOW_EXPIRED` / 409 |

Internal exception messages are never returned directly.

## Non-Functional Strategy

- Latency: ingestion target P95 <= 15s for common single-photo cases; use OCR/LLM timeout 30s
  and clear pending fallback rather than blocking indefinitely.
- Reliability: all external calls use timeout + at least one retry with exponential backoff.
- Privacy: private bucket, signed upload URL, authenticated read path, no service_role user query.
- Data isolation: all business tables have RLS; backend uses user JWT PostgREST for business data.
- Observability: log request id, error code, external call latency, prompt version, token counts;
  do not log openid, phone, original OCR text, or raw images.
- Offline-lite: capture flow creates an `ingest_sessions` row and local pending upload metadata so
  users can retry after network interruption.

## Required Tests

| Test group | Required cases |
|---|---|
| Auth | mock WeChat code exchange; first login creates user; repeated login returns tokens |
| Ingestion E2E | mock OCR + mock DeepSeek; photo happy path; PDF candidate path |
| LLM invalid JSON | invalid JSON twice returns pending candidate and writes `llm_calls` audit |
| OCR failure | OCR failure still allows manual save with image and user-entered question |
| RLS isolation | A/B tokens cannot list, get, patch, delete each other's rows or files |
| Tag normalization | 5 variants such as `二次函数顶点式`, `顶点式`, `二次函数（顶点式）` merge to 1 tag |
| Soft delete | delete hides item and decrements counts; restore within 7 days reverses it |
| Upload validation | jpg/png/pdf only; image 5MB, PDF 10MB/20 pages; oversized returns guidance |
| Today review | recent unopened mistakes appear; opening removes from list; empty state has two buttons |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| OCR segmentation of PDFs is imperfect | expose candidates, let user skip unreliable splits |
| LLM output drifts | strict JSON prompt, response format where available, Pydantic validation, retry once |
| Tag synonym map grows messy | start with deterministic normalization and user-scoped unique index |
| Signed URL misuse | short TTL, private bucket, object keys under user namespace |
| 15s target missed for large PDFs | PDF import may return candidates asynchronously later if needed; MVP keeps size/page limits |
| Frontend upload interruption | `ingest_sessions` plus local retry metadata |

## Non-Goals

MVP does not implement: 主动推送、相似题生成、错因深度归因、知识图谱、复习算法、
班级 / 家长 / 教师、多端、多语言、付费体系。任何要把它们拉进 MVP 的方案必须先改宪法。

## Phase Outputs

- `research.md`: OCR decision, reference-plan disposition, dependency list.
- `data-model.md`: tables, fields, constraints, RLS, indexes, migration-ready DDL.
- `contracts/openapi.yaml`: OpenAPI 3.1 contracts for auth, upload, mistakes, notes, tags,
  subjects, today-review.
- `quickstart.md`: 5-minute local setup and demo ingest path.

## Post-Design Constitution Check

Re-evaluation result: Pass. The generated design keeps user data behind RLS, avoids service_role
business queries, requires user confirmation before final mistake/note persistence, audits LLM calls,
keeps prompt files versioned, and preserves MVP non-goals.
