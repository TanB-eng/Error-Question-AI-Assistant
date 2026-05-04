# Quickstart: 错题与笔记智能辅导 MVP

This guide gets a developer from a fresh checkout to one local ingest demo in about 5 minutes once
external credentials are available.

## Prerequisites

- Python 3.11+
- uv
- Node.js and WeChat Mini Program developer tooling
- Supabase CLI
- Tencent Cloud OCR credentials
- DeepSeek API key
- WeChat Mini Program AppID and AppSecret

## 1. Backend setup

```powershell
cd backend
uv sync
```

Create `backend/.env`:

```env
APP_ENV=local
API_BASE_URL=http://localhost:8000

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=only-for-auth-bootstrap-and-migrations
SUPABASE_JWT_JWKS_URL=https://your-project.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_STORAGE_BUCKET=user-files

WECHAT_APP_ID=your-wechat-app-id
WECHAT_APP_SECRET=your-wechat-app-secret

DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

OCR_PROVIDER=tencent
TENCENT_SECRET_ID=your-secret-id
TENCENT_SECRET_KEY=your-secret-key
TENCENT_REGION=ap-guangzhou
```

Run the API:

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Supabase setup

Link the project:

```powershell
supabase login
supabase link --project-ref your-project-ref
```

Create a private bucket:

```powershell
supabase storage create user-files --private
```

Apply migration after `supabase/migrations/0001_init.sql` is created from `data-model.md`:

```powershell
supabase db push
```

Local reset path:

```powershell
supabase start
supabase db reset
```

## 3. Frontend setup

Create `frontend/project.config.json` with the real AppID:

```json
{
  "appid": "your-wechat-app-id",
  "projectname": "mistake-note-ai",
  "miniprogramRoot": "./",
  "setting": {
    "urlCheck": false
  }
}
```

Set local API base URL in frontend config:

```js
// frontend/services/config.js
export const API_BASE_URL = "http://localhost:8000";
```

Request flow expectations:

- `utils/request.js` injects `Authorization: Bearer <access_token>`.
- On 401, it refreshes once and retries the original request.
- Pages call `frontend/services/*`, not raw `wx.request` directly.

## 4. One local ingest demo

### Step A: Login

In the frontend:

1. Open login page.
2. Call `wx.login`.
3. POST `/auth/wx-login` with the returned `code`.
4. Store `access_token` and `refresh_token`.

Mock path for backend-only testing:

```powershell
uv run pytest tests/test_auth.py -k wx_login
```

### Step B: Sign upload

```http
POST /uploads/sign
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "mime_type": "image/jpeg",
  "scene": "mistake",
  "filename": "demo.jpg"
}
```

Expected result:

```json
{
  "signed_url": "https://...",
  "object_key": "users/<user_id>/mistakes/2026/05/<uuid>.jpg",
  "expires_in": 600
}
```

### Step C: Upload file directly to Storage

The frontend uses `wx.uploadFile` to PUT/POST to the signed URL. The file must be:

- jpg or png: max 5MB
- pdf: max 10MB and max 20 pages

Oversized files must show “请拆分上传或更换受支持文件”.

### Step D: Ingest mistake

```http
POST /mistakes/ingest
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "object_key": "users/<user_id>/mistakes/2026/05/<uuid>.jpg",
  "source_type": "photo",
  "subject_id": 1
}
```

Expected happy-path response:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000001",
  "status": "ready",
  "ocr_text": "已知二次函数...",
  "candidates": [
    {
      "subject_id": 1,
      "question": "已知二次函数...",
      "my_answer": "",
      "correct_answer": "",
      "knowledge_points": ["二次函数顶点式"],
      "question_type": "选择题",
      "difficulty": 3,
      "error_cause": "公式记忆错误",
      "analysis": ""
    }
  ],
  "error_code": null
}
```

Expected degraded response when DeepSeek JSON validation fails twice:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000001",
  "status": "pending_classification",
  "ocr_text": "已知二次函数...",
  "candidates": [],
  "error_code": "LLM_SCHEMA_INVALID"
}
```

### Step E: Save reviewed mistake

```http
POST /mistakes
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "ingest_session_id": "00000000-0000-0000-0000-000000000001",
  "subject_id": 1,
  "source_type": "photo",
  "object_key": "users/<user_id>/mistakes/2026/05/<uuid>.jpg",
  "ocr_text": "已知二次函数...",
  "question": "已知二次函数...",
  "my_answer": "",
  "correct_answer": "",
  "analysis": "",
  "question_type": "选择题",
  "difficulty": 3,
  "error_cause": "公式记忆错误",
  "status": "active",
  "answer_status": "unreviewed",
  "annotation": "",
  "tags": [
    { "kind": "knowledge_point", "name": "二次函数顶点式" },
    { "kind": "question_type", "name": "选择题" },
    { "kind": "error_cause", "name": "公式记忆错误" }
  ]
}
```

Verify:

```http
GET /tags?subject_id=1&kind=knowledge_point
Authorization: Bearer <access_token>
```

The response should include one normalized knowledge point tag. Repeating with “顶点式” should reuse
the same `normalized_name`.

## 5. Test commands

```powershell
cd backend
uv run ruff check .
uv run mypy app --strict
uv run pytest
```

Required test groups:

- WeChat login to Supabase JWT, with WeChat mocked.
- Photo/PDF ingest E2E with OCR and DeepSeek mocked.
- LLM invalid JSON fallback to pending.
- OCR failure fallback to manual save.
- RLS two-user isolation.
- Tag normalization variants collapse to one tag.
- Soft delete and restore within 7 days.

## 6. CI sketch

GitHub Actions must run on pull requests:

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: cd backend && uv sync
      - run: cd backend && uv run ruff check .
      - run: cd backend && uv run mypy app --strict
      - run: cd backend && uv run pytest
```
