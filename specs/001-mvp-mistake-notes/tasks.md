# Tasks: 错题与笔记智能辅导 MVP

**Feature**: `001-mvp-mistake-notes`  
**Input**: `plan.md`, `data-model.md`, `contracts/openapi.yaml`, `.specify/memory/constitution.md`  
**规则**: B(n) 全部完成后才能开 B(n+1)。每个任务约 0.5~1.5 天，对应一次 PR。

## 批次汇总

| 批次 | 目标 | 任务数 | 是否含可并行任务 |
|---|---|---:|---|
| B1 | 项目骨架与配置 | 8 | 是 |
| B2 | Supabase 与数据层 | 7 | 是 |
| B3 | 鉴权与 Storage | 12 | 是 |
| B4 | 录入主链（错题） | 15 | 是 |
| B5 | PDF 导入与笔记 | 10 | 是 |
| B6 | 浏览、校对、软删除 | 14 | 是 |
| B7 | 收尾与硬化 | 5 | 是 |
| **合计** |  | **71** | 是 |

## B1 · 项目骨架与配置（无业务逻辑）

- [X] T001 初始化仓库基础文件
  - 所属批次：B1
  - 依赖：-
  - 可并行：否
  - 涉及文件：`.gitignore`, `README.md`, `LICENSE`, `.pre-commit-config.yaml`
  - 完成定义（DoD）：
    - 新增 pre-commit 配置并包含 gitleaks hook
    - 通过 `pre-commit run --all-files`
    - 自动化用例：`scripts/check_gitleaks_config.ps1::gitleaks_hook_present`
  - 风险 / 注意：真实 `.env`、密钥、token 必须进入 `.gitignore`

- [X] T002 初始化后端 uv 工程与静态检查配置
  - 所属批次：B1
  - 依赖：T001
  - 可并行：否
  - 涉及文件：`backend/pyproject.toml`, `backend/uv.lock`, `backend/app/__init__.py`, `backend/tests/__init__.py`
  - 完成定义（DoD）：
    - `uv sync` 成功生成锁文件
    - `uv run ruff check .` 与 `uv run mypy app --strict` 可运行
    - 自动化用例：`backend/tests/test_tooling.py::test_pyproject_enables_strict_checks`
  - 风险 / 注意：包管理锁定 uv，不引入 poetry

- [X] T003 实现 Settings 与环境变量样例及原始环境读取扫描
  - 所属批次：B1
  - 依赖：T002
  - 可并行：否
  - 涉及文件：`backend/app/core/settings.py`, `backend/.env.example`, `scripts/check_no_raw_getenv.py`, `backend/tests/core/test_settings.py`
  - 完成定义（DoD）：
    - `.env.example` 覆盖 Supabase、DeepSeek、OCR、WeChat、Storage、JWT 变量
    - 业务代码只通过 `settings.xxx` 读取配置
    - `scripts/check_no_raw_getenv.py` 校验 `backend/app/` 中除 `core/settings.py` 外不得出现 `os.getenv`/`os.environ`
    - 自动化用例：`backend/tests/core/test_settings.py::test_env_example_matches_settings_fields`
  - 风险 / 注意：宪法红线，禁止真实 key 入库，禁止散落 `os.getenv`

- [X] T004 实现 FastAPI 应用入口与健康检查
  - 所属批次：B1
  - 依赖：T002
  - 可并行：否
  - 涉及文件：`backend/app/main.py`, `backend/tests/test_healthz.py`
  - 完成定义（DoD）：
    - `GET /healthz` 返回 `{ "status": "ok" }`
    - `uv run pytest backend/tests/test_healthz.py` 通过
    - 自动化用例：`backend/tests/test_healthz.py::test_healthz_ok`
  - 风险 / 注意：健康检查不得输出环境变量或密钥

- [X] T005 配置 GitHub Actions 基础 CI
  - 所属批次：B1
  - 依赖：T002, T003, T004
  - 可并行：否
  - 涉及文件：`.github/workflows/ci.yml`
  - 完成定义（DoD）：
    - CI 包含 uv sync、ruff、mypy strict、pytest、gitleaks、`scripts/check_no_raw_getenv.py`
    - CI 包含 gitleaks self-test fixture，验证疑似 key 能被拦截
    - 本地可用 `act` 或 workflow lint 检查基本语法
    - 自动化用例：`scripts/check_ci.py::test_ci_contains_required_jobs`
  - 风险 / 注意：宪法第 8 条，CI 红灯不得合入 main

- [X] T006 [P] 创建 frontend 小程序工程骨架
  - 所属批次：B1
  - 依赖：T001
  - 可并行：是 [P]
  - 涉及文件：`frontend/app.json`, `frontend/app.js`, `frontend/app.wxss`, `frontend/project.config.json`, `frontend/pages/login/*`, `frontend/pages/home/*`
  - 完成定义（DoD）：
    - 微信开发者工具可打开 `frontend/`
    - `project.config.json` 使用 AppID 占位符，不含 secret
    - 自动化用例：`frontend/tests/app-config.test.js::app_json_declares_login_and_home`
  - 风险 / 注意：只创建骨架，不接入业务请求

- [X] T007 [P] 创建 frontend 请求工具骨架
  - 所属批次：B1
  - 依赖：T006
  - 可并行：是 [P]
  - 涉及文件：`frontend/utils/request.js`, `frontend/services/config.js`, `frontend/tests/request.test.js`
  - 完成定义（DoD）：
    - `request.js` 暴露统一请求函数但暂不注入 JWT
    - 页面不得直接调用裸 `wx.request`
    - 自动化用例：`frontend/tests/request.test.js::test_request_exports_basic_wrapper`
  - 风险 / 注意：小程序端不得出现第三方 secret

- [X] T008 [P] 复核 quickstart 初版与本地启动说明
  - 所属批次：B1
  - 依赖：T002, T006
  - 可并行：是 [P]
  - 涉及文件：`specs/001-mvp-mistake-notes/quickstart.md`, `README.md`
  - 完成定义（DoD）：
    - quickstart 中使用 `frontend/` 路径
    - README 指向 spec、plan、quickstart
    - 自动化用例：`scripts/check_docs.py::test_quickstart_references_frontend_path`
  - 风险 / 注意：不要把文档任务扩成独立文档工程

## B2 · Supabase 与数据层

- [X] T009 编写 0001 初始化建表迁移
  - 所属批次：B2
  - 依赖：T003
  - 可并行：否
  - 涉及文件：`supabase/migrations/0001_init.sql`, `backend/tests/db/test_migrations.py`
  - 完成定义（DoD）：
    - 建表包含 `users`, `subjects`, `tags`, `mistakes`, `notes`, `mistake_tags`, `note_tags`, `ingest_sessions`, `llm_calls`
    - 所有业务表含 `user_id`, `created_at`, 需软删除的表含 `deleted_at`
    - 自动化用例：`backend/tests/db/test_migrations.py::test_0001_init_schema_applies`
  - 风险 / 注意：涉及用户数据，必须保留 UUID 主键与显式外键策略

- [X] T010 编写初始化 schema 结构测试
  - 所属批次：B2
  - 依赖：T009
  - 可并行：否
  - 涉及文件：`backend/tests/db/test_schema_constraints.py`
  - 完成定义（DoD）：
    - 校验标签唯一索引 `(user_id, subject_id, kind, normalized_name)`
    - 校验 `llm_calls` 审计字段完整
    - 自动化用例：`backend/tests/db/test_schema_constraints.py::test_tags_unique_normalized_name`
  - 风险 / 注意：测试必须能在本地 Supabase 或测试 Postgres 中一键运行

- [X] T011 编写 0002 RLS 策略迁移
  - 所属批次：B2
  - 依赖：T009, T010
  - 可并行：否
  - 涉及文件：`supabase/migrations/0002_rls.sql`
  - 完成定义（DoD）：
    - 所有业务表启用 RLS
    - 策略统一使用 `auth.uid() = user_id`
    - 自动化用例：`backend/tests/test_rls.py::test_all_business_tables_enable_rls`
  - 风险 / 注意：宪法红线，任何业务表不得缺 RLS

- [X] T012 编写 RLS 双用户隔离冒烟测试
  - 所属批次：B2
  - 依赖：T011
  - 可并行：否
  - 涉及文件：`backend/tests/test_rls.py`, `backend/tests/fixtures/supabase_tokens.py`
  - 完成定义（DoD）：
    - A token 不能读取 B 的错题、笔记、标签、会话
    - 互访返回 403 或空结果
    - 自动化用例：`backend/tests/test_rls.py::test_two_users_cannot_read_each_other_business_rows`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [X] T013 [P] 编写 0003 学科字典种子迁移
  - 所属批次：B2
  - 依赖：T009
  - 可并行：是 [P]
  - 涉及文件：`supabase/migrations/0003_seed_subjects.sql`, `backend/tests/db/test_subject_seed.py`
  - 完成定义（DoD）：
    - 种子包含 10 个锁定学科
    - 重复执行不产生重复数据
    - 自动化用例：`backend/tests/db/test_subject_seed.py::test_subject_seed_is_idempotent`
  - 风险 / 注意：学科为固定字典，本期不允许用户新增

- [X] T014 [P] 实现 Supabase 两类 client
  - 所属批次：B2
  - 依赖：T003
  - 可并行：是 [P]
  - 涉及文件：`backend/app/core/supabase.py`, `backend/tests/core/test_supabase_client.py`
  - 完成定义（DoD）：
    - 提供 user-jwt client 与 service-role client 工厂
    - service-role client 函数名和注释明确仅限 auth bootstrap/migration/admin
    - 自动化用例：`backend/tests/core/test_supabase_client.py::test_user_client_uses_bearer_jwt`
  - 风险 / 注意：宪法红线，业务查询不得使用 service_role

- [X] T015 [P] 编写 Supabase client 使用边界测试
  - 所属批次：B2
  - 依赖：T014
  - 可并行：是 [P]
  - 涉及文件：`backend/tests/core/test_supabase_client_boundaries.py`
  - 完成定义（DoD）：
    - 测试业务 service 无法导入 admin client
    - 静态扫描阻止 `service_role` 出现在 `backend/app/services/` 业务查询中
    - 自动化用例：`backend/tests/core/test_supabase_client_boundaries.py::test_services_do_not_use_admin_client`
  - 风险 / 注意：接触用户数据边界，必须通过 RLS 双用户隔离测试

## B3 · 鉴权与 Storage

- [X] T016 校对 /auth/wx-login schema 与契约
  - 所属批次：B3
  - 依赖：T014
  - 可并行：否
  - 涉及文件：`backend/app/schemas/auth.py`, `specs/001-mvp-mistake-notes/contracts/openapi.yaml`, `backend/tests/contracts/test_auth_contract.py`
  - 完成定义（DoD）：
    - `WxLoginRequest` 与 `AuthSessionResponse` 和 OpenAPI 一致
    - contract 测试覆盖 code、access_token、refresh_token、user_profile
    - 自动化用例：`backend/tests/contracts/test_auth_contract.py::test_wx_login_schema_matches_openapi`
  - 风险 / 注意：openid 不得写入日志

- [X] T017 实现微信登录换 Supabase JWT service
  - 所属批次：B3
  - 依赖：T016
  - 可并行：否
  - 涉及文件：`backend/app/services/auth.py`, `backend/app/core/wechat.py`, `backend/tests/services/test_auth_service.py`
  - 完成定义（DoD）：
    - mock 微信 code exchange 后创建/复用用户
    - service_role 仅用于创建用户资料
    - 自动化用例：`backend/tests/services/test_auth_service.py::test_wx_login_creates_user_with_admin_only_for_bootstrap`
  - 风险 / 注意：涉及 service_role，禁止用于业务表用户级查询

- [X] T018 实现 POST /auth/wx-login 路由
  - 所属批次：B3
  - 依赖：T017
  - 可并行：否
  - 涉及文件：`backend/app/api/auth.py`, `backend/app/main.py`, `backend/tests/api/test_auth_api.py`
  - 完成定义（DoD）：
    - 路由只解析参数并调用 auth service
    - 错误返回统一错误码，不暴露微信内部异常
    - 自动化用例：`backend/tests/api/test_auth_api.py::test_wx_login_returns_session_tokens`
  - 风险 / 注意：路由层不得直接访问数据库

- [X] T019 编写微信登录集成测试
  - 所属批次：B3
  - 依赖：T018
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_auth_wx_login.py`
  - 完成定义（DoD）：
    - mock 微信侧，完成首次登录与重复登录
    - 断言不会记录 openid、AppSecret、token
    - 自动化用例：`backend/tests/integration/test_auth_wx_login.py::test_wx_login_e2e_with_mock_wechat`
  - 风险 / 注意：接触用户身份数据，必须通过 RLS 双用户隔离测试

- [X] T020 实现 current_user 依赖
  - 所属批次：B3
  - 依赖：T018
  - 可并行：否
  - 涉及文件：`backend/app/deps.py`, `backend/tests/test_deps.py`
  - 完成定义（DoD）：
    - 从 Bearer JWT 解出 `user_id`
    - 缺失/过期 token 返回 `AUTH_REQUIRED` 或 `TOKEN_EXPIRED`
    - 自动化用例：`backend/tests/test_deps.py::test_current_user_rejects_missing_token`
  - 风险 / 注意：鉴权失败不得降级为匿名业务访问

- [X] T021 校对 /uploads/sign schema 与契约
  - 所属批次：B3
  - 依赖：T020
  - 可并行：否
  - 涉及文件：`backend/app/schemas/uploads.py`, `backend/tests/contracts/test_upload_contract.py`
  - 完成定义（DoD）：
    - schema 限定 `image/jpeg`, `image/png`, `application/pdf`
    - schema 限定 scene 为 `mistake|note`
    - `mime_type=application/pdf` 时 signed URL 元数据或后续校验策略声明最大 10MB，ingest 阶段二次确认页数最多 20 页
    - 自动化用例：`backend/tests/contracts/test_upload_contract.py::test_upload_sign_schema_matches_openapi`
  - 风险 / 注意：签名接口必须 JWT 必填

- [X] T022 实现 Storage 签名 service
  - 所属批次：B3
  - 依赖：T021
  - 可并行：否
  - 涉及文件：`backend/app/services/uploads.py`, `backend/tests/services/test_uploads_service.py`
  - 完成定义（DoD）：
    - object_key 命名空间包含当前 `user_id`
    - signed URL TTL 有上限
    - 自动化用例：`backend/tests/services/test_uploads_service.py::test_signed_object_key_is_namespaced_by_user`
  - 风险 / 注意：接触用户文件，必须通过 RLS 双用户隔离测试；bucket 默认 private

- [X] T023 实现 POST /uploads/sign 路由
  - 所属批次：B3
  - 依赖：T022
  - 可并行：否
  - 涉及文件：`backend/app/api/uploads.py`, `backend/app/main.py`, `backend/tests/api/test_uploads_api.py`
  - 完成定义（DoD）：
    - 路由通过 `current_user` 注入 user_id
    - 路由返回 `signed_url`, `object_key`, `expires_in`
    - 自动化用例：`backend/tests/api/test_uploads_api.py::test_upload_sign_requires_jwt`
  - 风险 / 注意：路由不得直接调用 Supabase Storage SDK

- [X] T024 编写上传与 signed GET 集成测试
  - 所属批次：B3
  - 依赖：T023
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_storage_signed_upload.py`
  - 完成定义（DoD）：
    - 用 signed PUT 上传一张测试图后可用 owner signed GET 取回
    - B 用户不能获取 A 用户 object_key
    - 自动化用例：`backend/tests/integration/test_storage_signed_upload.py::test_upload_then_signed_get_owner_only`
  - 风险 / 注意：接触用户文件，必须通过 RLS 双用户隔离测试

- [X] T025 [P] 实现 frontend JWT 注入与 401 刷新
  - 所属批次：B3
  - 依赖：T020
  - 可并行：是 [P]
  - 涉及文件：`frontend/utils/request.js`, `frontend/services/auth.js`, `frontend/tests/request-auth.test.js`
  - 完成定义（DoD）：
    - 请求自动注入 Bearer JWT
    - 401 后 refresh 一次并重试原请求
    - 自动化用例：`frontend/tests/request-auth.test.js::test_refresh_once_then_retry_original_request`
  - 风险 / 注意：frontend 只保存短期 token，不保存任何 service_role key

- [X] T026 [P] 实现 frontend 登录页
  - 所属批次：B3
  - 依赖：T018, T025
  - 可并行：是 [P]
  - 涉及文件：`frontend/pages/login/*`, `frontend/services/auth.js`, `frontend/tests/login.test.js`
  - 完成定义（DoD）：
    - `wx.login` 后调用 `/auth/wx-login`
    - token 持久化后跳转 home
    - 自动化用例：`frontend/tests/login.test.js::test_login_page_stores_tokens_after_wx_login`
  - 风险 / 注意：不得在 frontend 存储微信 AppSecret

- [X] T026a 端到端补强 T012：用真实 A/B JWT 验证 RLS 互访
  - 所属批次：B3
  - 依赖：T026
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_rls_e2e.py`
  - 完成定义（DoD）：
    - 用 `/auth/wx-login` 真实签发 A、B 两个用户的 JWT
    - A 的 JWT 通过 PostgREST 访问 `mistakes`、`notes`、`tags`、`ingest_sessions` 只能看到自己的行，访问 B 的 row id 返回 404 或空结果
    - 自动化用例：`backend/tests/integration/test_rls_e2e.py::test_two_real_users_rls_isolation`
  - 风险 / 注意：如果失败说明 JWT claim 与 RLS policy 不匹配，常见原因是 JWT 里用户标识与 `auth.uid()` 解析路径不一致；接触用户数据，必须通过真实双用户隔离测试

## B4 · 录入主链（错题，最关键）

- [ ] T027 实现 OCR 抽象接口与腾讯云实现
  - 所属批次：B4
  - 依赖：T003
  - 可并行：否
  - 涉及文件：`backend/app/services/ocr.py`, `backend/app/core/ocr_client.py`, `backend/tests/services/test_ocr.py`
  - 完成定义（DoD）：
    - 定义 OCR 抽象接口、腾讯云实现、测试 mock 实现
    - 外部调用有超时与至少一次重试
    - 自动化用例：`backend/tests/services/test_ocr.py::test_ocr_client_retries_once_on_timeout`
  - 风险 / 注意：CI 禁止真调 OCR；用户原图不得发给 DeepSeek

- [ ] T028 编写 OCR 失败降级测试
  - 所属批次：B4
  - 依赖：T027
  - 可并行：否
  - 涉及文件：`backend/tests/services/test_ocr_fallback.py`
  - 完成定义（DoD）：
    - OCR 失败返回可手填保存的 pending 输入
    - 不吞异常，返回结构化错误码
    - 自动化用例：`backend/tests/services/test_ocr_fallback.py::test_ocr_failure_allows_manual_save`
  - 风险 / 注意：涉及用户数据，不得丢失已上传 object_key

- [ ] T029 实现错题分类 prompt 与 ClassifyResult schema
  - 所属批次：B4
  - 依赖：T027
  - 可并行：否
  - 涉及文件：`backend/app/services/prompts/classify_mistake_v1.md`, `backend/app/schemas/classify.py`, `backend/tests/schemas/test_classify_schema.py`
  - 完成定义（DoD）：
    - schema 字段覆盖 subject/question/my_answer/correct_answer/knowledge_points/question_type/difficulty/error_cause/analysis
    - difficulty 允许 null 或 1-5
    - 自动化用例：`backend/tests/schemas/test_classify_schema.py::test_classify_result_accepts_empty_strings_and_null_difficulty`
  - 风险 / 注意：Prompt 必须落盘并带版本号

- [ ] T030 实现 DeepSeek 统一 client
  - 所属批次：B4
  - 依赖：T029
  - 可并行：否
  - 涉及文件：`backend/app/services/llm/deepseek.py`, `backend/app/services/classifier.py`, `backend/tests/services/test_deepseek_client.py`
  - 完成定义（DoD）：
    - 强制 JSON 输出，失败重试 1 次
    - 写入 `llm_calls` 审计字段
    - 自动化用例：`backend/tests/services/test_deepseek_client.py::test_invalid_json_retries_once`
  - 风险 / 注意：LLM 相关任务必须覆盖非法 JSON 输出走 pending 分支；CI 禁止真调 DeepSeek

- [ ] T031 编写 DeepSeek 非法 JSON pending 分支测试
  - 所属批次：B4
  - 依赖：T030
  - 可并行：否
  - 涉及文件：`backend/tests/services/test_classifier.py`
  - 完成定义（DoD）：
    - DeepSeek 二次返回非法 JSON 时返回 `pending_classification`
    - `llm_calls.schema_hit=false` 且 `retry_count=1`
    - 自动化用例：`backend/tests/services/test_classifier.py::test_invalid_json_twice_returns_pending`
  - 风险 / 注意：宪法红线，模型结果未校验不得进入业务逻辑

- [ ] T032 实现标签规范化与归并 service
  - 所属批次：B4
  - 依赖：T009, T013
  - 可并行：否
  - 涉及文件：`backend/app/services/tag_normalizer.py`, `backend/tests/services/test_tag_normalizer.py`
  - 完成定义（DoD）：
    - 实现去空格、全角转半角、括号统一、末尾标点清理
    - 按 `(user_id, subject_id, kind, normalized_name)` upsert
    - 自动化用例：`backend/tests/services/test_tag_normalizer.py::test_normalize_basic_chinese_variants`
  - 风险 / 注意：接触用户标签，必须通过 RLS 双用户隔离测试

- [ ] T033 编写 5 种标签写法归并测试
  - 所属批次：B4
  - 依赖：T032
  - 可并行：否
  - 涉及文件：`backend/tests/services/test_tag_normalizer.py`
  - 完成定义（DoD）：
    - 5 种知识点写法归并为 1 个 tag
    - 不同用户同名标签不互相复用
    - 自动化用例：`backend/tests/services/test_tag_normalizer.py::test_five_variants_merge_to_one_user_scoped_tag`
  - 风险 / 注意：涉及用户数据，必须通过 RLS 双用户隔离测试

- [ ] T034 校对 POST /mistakes/ingest schema 与契约
  - 所属批次：B4
  - 依赖：T029
  - 可并行：否
  - 涉及文件：`backend/app/schemas/mistakes.py`, `backend/tests/contracts/test_mistakes_ingest_contract.py`
  - 完成定义（DoD）：
    - request 包含 object_key/source_type/subject_id
    - response 包含 session_id/status/ocr_text/candidates/error_code
    - 自动化用例：`backend/tests/contracts/test_mistakes_ingest_contract.py::test_mistake_ingest_schema_matches_openapi`
  - 风险 / 注意：ingest 只返回候选，不落最终业务表

- [ ] T035 实现错题 ingest 编排 service
  - 所属批次：B4
  - 依赖：T024, T028, T031, T032, T034
  - 可并行：否
  - 涉及文件：`backend/app/services/ingestion.py`, `backend/tests/services/test_ingestion.py`
  - 完成定义（DoD）：
    - 编排拉文件、OCR、DeepSeek 分类、返回候选
    - OCR 失败和 LLM 失败均返回 pending 分支
    - 自动化用例：`backend/tests/services/test_ingestion.py::test_photo_ingest_returns_ready_candidate_with_mocks`
  - 风险 / 注意：涉及用户文件，必须通过 RLS 双用户隔离测试；LLM 非法 JSON 必须走 pending

- [ ] T036 实现 POST /mistakes/ingest 路由
  - 所属批次：B4
  - 依赖：T035
  - 可并行：否
  - 涉及文件：`backend/app/api/mistakes.py`, `backend/app/main.py`, `backend/tests/api/test_mistakes_ingest_api.py`
  - 完成定义（DoD）：
    - 路由只调用 ingestion service，不直接访问 OCR/LLM/Supabase
    - 未登录请求返回 401
    - 自动化用例：`backend/tests/api/test_mistakes_ingest_api.py::test_mistake_ingest_requires_jwt`
  - 风险 / 注意：路由层不得直接调用大模型

- [ ] T037 编写错题 ingest 集成测试
  - 所属批次：B4
  - 依赖：T036
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_mistake_ingest.py`
  - 完成定义（DoD）：
    - mock OCR + mock DeepSeek 正常路径返回候选
    - DeepSeek 非法 JSON 二次失败返回 pending
    - 自动化用例：`backend/tests/integration/test_mistake_ingest.py::test_ingest_invalid_json_pending_branch`
  - 风险 / 注意：LLM/OCR 必须 mock；接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T038 校对 POST /mistakes schema 与契约
  - 所属批次：B4
  - 依赖：T034
  - 可并行：否
  - 涉及文件：`backend/app/schemas/mistakes.py`, `backend/tests/contracts/test_mistake_create_contract.py`
  - 完成定义（DoD）：
    - create request 包含校对后的最终字段和 tags
    - create 接口以请求体 `subject_id` 为最终值，ingest 阶段模型返回的 subject 仅作建议且不得覆盖用户提交值
    - schema 不接受裸 dict 出入参
    - 自动化用例：`backend/tests/contracts/test_mistake_create_contract.py::test_mistake_create_schema_matches_openapi`
  - 风险 / 注意：最终落库必须来自用户校对字段

- [ ] T039 实现错题保存与标签 upsert service
  - 所属批次：B4
  - 依赖：T032, T038
  - 可并行：否
  - 涉及文件：`backend/app/services/mistakes.py`, `backend/tests/services/test_mistakes_create.py`
  - 完成定义（DoD）：
    - 保存 mistake 后 upsert tags 与 mistake_tags
    - pending 状态可保存
    - 自动化用例：`backend/tests/services/test_mistakes_create.py::test_create_mistake_upserts_normalized_tags`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T040 实现 POST /mistakes 路由
  - 所属批次：B4
  - 依赖：T039
  - 可并行：否
  - 涉及文件：`backend/app/api/mistakes.py`, `backend/tests/api/test_mistakes_create_api.py`
  - 完成定义（DoD）：
    - 路由注入 current_user 并调用 service
    - 返回创建后的 MistakeDetail
    - 自动化用例：`backend/tests/api/test_mistakes_create_api.py::test_create_mistake_returns_detail`
  - 风险 / 注意：路由层不得直接访问数据库

- [ ] T041 编写错题保存端到端集成测试
  - 所属批次：B4
  - 依赖：T040
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_mistake_create_e2e.py`
  - 完成定义（DoD）：
    - OCR 失败后仍可手填并保存
    - 标签 5 种写法归并为 1 个标签
    - 自动化用例：`backend/tests/integration/test_mistake_create_e2e.py::test_ocr_failure_manual_save_and_tag_merge`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

## B5 · PDF 导入与笔记

- [ ] T042 实现 PDF 文本提取与规则切分 service
  - 所属批次：B5
  - 依赖：T027, T035
  - 可并行：否
  - 涉及文件：`backend/app/services/pdf.py`, `backend/app/services/ocr.py`, `backend/tests/services/test_pdf_split.py`
  - 完成定义（DoD）：
    - 支持 PDF 最大 10MB / 20 页校验
    - 规则切分返回多题候选
    - 自动化用例：`backend/tests/services/test_pdf_split.py::test_pdf_split_returns_multiple_candidates`
  - 风险 / 注意：CI 禁止真调 OCR；复杂切分留扩展点

- [ ] T043 编写 PDF 多题切分测试
  - 所属批次：B5
  - 依赖：T042
  - 可并行：否
  - 涉及文件：`backend/tests/services/test_pdf_split.py`, `backend/tests/fixtures/sample_exam.pdf`
  - 完成定义（DoD）：
    - sample PDF 切出至少 2 个候选
    - 超过页数或大小限制返回 `UPLOAD_LIMIT_EXCEEDED`
    - 自动化用例：`backend/tests/services/test_pdf_split.py::test_pdf_over_limit_returns_upload_limit_error`
  - 风险 / 注意：测试 fixture 不得包含真实学生数据

- [ ] T044 扩展 /mistakes/ingest 支持 PDF
  - 所属批次：B5
  - 依赖：T042, T043
  - 可并行：否
  - 涉及文件：`backend/app/services/ingestion.py`, `backend/app/api/mistakes.py`, `backend/tests/integration/test_mistake_ingest_pdf.py`
  - 完成定义（DoD）：
    - `source_type=pdf` 返回多题候选
    - 用户只勾选的候选进入后续保存
    - 自动化用例：`backend/tests/integration/test_mistake_ingest_pdf.py::test_pdf_ingest_returns_multiple_review_candidates`
  - 风险 / 注意：接触用户文件，必须通过 RLS 双用户隔离测试；OCR/LLM 必须 mock

- [ ] T045 校对 /notes/ingest 与 notes CRUD schema 契约
  - 所属批次：B5
  - 依赖：T038
  - 可并行：否
  - 涉及文件：`backend/app/schemas/notes.py`, `backend/tests/contracts/test_notes_contract.py`
  - 完成定义（DoD）：
    - 笔记 schema 不包含 difficulty/question_type/error_cause
    - 覆盖 `/notes/ingest`, `POST /notes`, `GET /notes`, `GET/PATCH/DELETE /notes/{id}`, restore
    - 自动化用例：`backend/tests/contracts/test_notes_contract.py::test_note_schemas_match_openapi`
  - 风险 / 注意：所有接口 JWT 必填

- [ ] T046 实现笔记 ingest service
  - 所属批次：B5
  - 依赖：T029, T035, T045
  - 可并行：否
  - 涉及文件：`backend/app/services/prompts/classify_note_v1.md`, `backend/app/services/notes.py`, `backend/tests/services/test_note_ingest.py`
  - 完成定义（DoD）：
    - OCR 后返回笔记内容、学科、知识点候选
    - `backend/app/services/prompts/classify_note_v1.md` 存在、文件名带版本号，文件内容包含 prompt 版本标识
    - LLM 非法 JSON 二次失败返回 pending
    - 自动化用例：`backend/tests/services/test_note_ingest.py::test_note_invalid_json_twice_returns_pending`
  - 风险 / 注意：LLM 相关任务必须覆盖非法 JSON 输出走 pending 分支

- [ ] T047 实现 POST /notes/ingest 路由
  - 所属批次：B5
  - 依赖：T046
  - 可并行：否
  - 涉及文件：`backend/app/api/notes.py`, `backend/app/main.py`, `backend/tests/api/test_notes_ingest_api.py`
  - 完成定义（DoD）：
    - 路由只调用 notes ingest service
    - 未登录请求返回 401
    - 自动化用例：`backend/tests/api/test_notes_ingest_api.py::test_note_ingest_requires_jwt`
  - 风险 / 注意：路由层不得直接调用 OCR/LLM

- [ ] T048 编写笔记 ingest 集成测试
  - 所属批次：B5
  - 依赖：T047
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_note_ingest.py`
  - 完成定义（DoD）：
    - mock OCR + mock DeepSeek 返回笔记候选
    - 非法 JSON 走 pending 分支
    - 自动化用例：`backend/tests/integration/test_note_ingest.py::test_note_ingest_e2e_with_invalid_json_pending`
  - 风险 / 注意：LLM/OCR 必须 mock；接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T049 实现 POST /notes 保存接口
  - 所属批次：B5
  - 依赖：T045, T046
  - 可并行：否
  - 涉及文件：`backend/app/services/notes.py`, `backend/app/api/notes.py`, `backend/tests/api/test_notes_create_api.py`
  - 完成定义（DoD）：
    - 保存 note 并 upsert knowledge_point tags / note_tags
    - 不要求题型、难度、错因字段
    - 自动化用例：`backend/tests/api/test_notes_create_api.py::test_create_note_upserts_knowledge_tags`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T050 [P] 实现 GET/PATCH/DELETE /notes 基础接口
  - 所属批次：B5
  - 依赖：T045, T049
  - 可并行：是 [P]
  - 涉及文件：`backend/app/services/notes.py`, `backend/app/api/notes.py`, `backend/tests/api/test_notes_crud_api.py`
  - 完成定义（DoD）：
    - 支持列表、详情、更新、软删除
    - 软删除后普通列表不返回
    - 自动化用例：`backend/tests/api/test_notes_crud_api.py::test_note_soft_delete_hides_from_active_list`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T051 [P] 编写笔记端到端测试
  - 所属批次：B5
  - 依赖：T048, T049, T050
  - 可并行：是 [P]
  - 涉及文件：`backend/tests/integration/test_notes_e2e.py`
  - 完成定义（DoD）：
    - 笔记图片/PDF ingest 到保存全链路通过
    - A 用户看不到 B 用户笔记
    - 自动化用例：`backend/tests/integration/test_notes_e2e.py::test_note_e2e_owner_only`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

## B6 · 浏览、校对、软删除

- [ ] T052 校对 GET /mistakes 列表 schema 与契约
  - 所属批次：B6
  - 依赖：T041
  - 可并行：否
  - 涉及文件：`backend/app/schemas/mistakes.py`, `backend/tests/contracts/test_mistake_list_contract.py`
  - 完成定义（DoD）：
    - 支持 subject_id/tag_id/status/page/page_size 过滤参数
    - status 支持 active/pending/trashed
    - 自动化用例：`backend/tests/contracts/test_mistake_list_contract.py::test_mistake_list_query_matches_openapi`
  - 风险 / 注意：列表必须只返回当前用户数据

- [ ] T053 实现 GET /mistakes service
  - 所属批次：B6
  - 依赖：T052
  - 可并行：否
  - 涉及文件：`backend/app/services/mistakes.py`, `backend/tests/services/test_mistakes_list.py`
  - 完成定义（DoD）：
    - 实现 subject/tag/status/page 过滤
    - active 默认排除 `deleted_at is not null`
    - 自动化用例：`backend/tests/services/test_mistakes_list.py::test_list_filters_by_subject_tag_and_status`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T054 实现 GET /mistakes 路由与集成测试
  - 所属批次：B6
  - 依赖：T053
  - 可并行：否
  - 涉及文件：`backend/app/api/mistakes.py`, `backend/tests/integration/test_mistakes_list.py`
  - 完成定义（DoD）：
    - 路由调用 list service 并返回分页结构
    - A/B 用户列表互相不可见
    - 自动化用例：`backend/tests/integration/test_mistakes_list.py::test_list_mistakes_rls_two_users`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T055 校对错题详情、更新、删除、恢复 schema 契约
  - 所属批次：B6
  - 依赖：T052
  - 可并行：否
  - 涉及文件：`backend/app/schemas/mistakes.py`, `backend/tests/contracts/test_mistake_mutation_contract.py`
  - 完成定义（DoD）：
    - 覆盖 `GET/PATCH/DELETE /mistakes/{id}` 和 `POST /mistakes/{id}/restore`
    - restore 409 错误码契约存在
    - 自动化用例：`backend/tests/contracts/test_mistake_mutation_contract.py::test_mistake_restore_contract_matches_openapi`
  - 风险 / 注意：删除必须软删除

- [ ] T056 实现错题详情、更新、软删除、恢复 service
  - 所属批次：B6
  - 依赖：T055
  - 可并行：否
  - 涉及文件：`backend/app/services/mistakes.py`, `backend/tests/services/test_mistake_mutations.py`
  - 完成定义（DoD）：
    - 更新标签后重新计算关联
    - 7 天内可恢复，超期返回 `RESTORE_WINDOW_EXPIRED`
    - 自动化用例：`backend/tests/services/test_mistake_mutations.py::test_restore_within_7_days_and_reject_expired`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T057 实现错题详情、更新、软删除、恢复路由
  - 所属批次：B6
  - 依赖：T056
  - 可并行：否
  - 涉及文件：`backend/app/api/mistakes.py`, `backend/tests/api/test_mistake_mutations_api.py`
  - 完成定义（DoD）：
    - 路由只调用 service，不直接访问数据库
    - 删除返回 204，恢复返回 MistakeDetail
    - 自动化用例：`backend/tests/api/test_mistake_mutations_api.py::test_delete_and_restore_routes`
  - 风险 / 注意：路由层不得直接访问数据库

- [ ] T058 编写错题软删除与恢复集成测试
  - 所属批次：B6
  - 依赖：T057
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_mistake_soft_delete_restore.py`
  - 完成定义（DoD）：
    - 删除后标签出错次数减 1
    - 标签下错题数为 0 时隐藏
    - 自动化用例：`backend/tests/integration/test_mistake_soft_delete_restore.py::test_delete_updates_tag_counts_and_restore_reverses`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T059 校对 /tags、/subjects、/today-review schema 契约
  - 所属批次：B6
  - 依赖：T052
  - 可并行：否
  - 涉及文件：`backend/app/schemas/tags.py`, `backend/app/schemas/subjects.py`, `backend/app/schemas/today_review.py`, `backend/tests/contracts/test_browse_contracts.py`
  - 完成定义（DoD）：
    - `/tags` 返回标签和出错次数聚合
    - `/today-review` empty_state 含两个按钮
    - 自动化用例：`backend/tests/contracts/test_browse_contracts.py::test_today_review_empty_state_contract`
  - 风险 / 注意：所有端点 JWT 必填

- [ ] T060 实现 /tags、/subjects、/today-review services 与 routes
  - 所属批次：B6
  - 依赖：T059
  - 可并行：否
  - 涉及文件：`backend/app/services/tags.py`, `backend/app/services/subjects.py`, `backend/app/services/today_review.py`, `backend/app/api/tags.py`, `backend/app/api/subjects.py`, `backend/app/api/today_review.py`
  - 完成定义（DoD）：
    - `/tags` 按 subject_id/kind 聚合未删除错题数
    - `/today-review` 返回最近 7 天新增且未再次打开过的错题
    - 自动化用例：`backend/tests/api/test_browse_api.py::test_tags_subjects_today_review_routes`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试；已知偏离“一端点一组任务”，因 `/subjects` 与 `/tags` 为简单只读 GET、`/today-review` 已由独立集成测试 T061 约束，故在本任务合并实现但不得继续扩展复习算法

- [ ] T061 编写浏览聚合与今日待复习集成测试
  - 所属批次：B6
  - 依赖：T060
  - 可并行：否
  - 涉及文件：`backend/tests/integration/test_browse_and_today_review.py`
  - 完成定义（DoD）：
    - 最近 7 天未打开错题出现在 today-review，打开后消失
    - `/tags` 隐藏 0 题标签
    - 自动化用例：`backend/tests/integration/test_browse_and_today_review.py::test_today_review_and_tag_counts`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T062 [P] 实现 frontend 首页、录入页与校对页
  - 所属批次：B6
  - 依赖：T041, T044
  - 可并行：是 [P]
  - 涉及文件：`frontend/pages/home/*`, `frontend/pages/capture/*`, `frontend/pages/review-form/*`, `frontend/services/mistakes.js`, `frontend/tests/review-form.test.js`
  - 完成定义（DoD）：
    - 上传前必须选择学科，未选提示用户先选择
    - 校对页可修改题干、答案、学科、知识点、难度、错因
    - 自动化用例：`frontend/tests/review-form.test.js::test_review_form_requires_subject_before_upload`
  - 风险 / 注意：校对页是关键交互，AI 结果不得绕过用户确认直接保存

- [ ] T063 [P] 实现 frontend 列表、详情、笔记、今日待复习页
  - 所属批次：B6
  - 依赖：T050, T061
  - 可并行：是 [P]
  - 涉及文件：`frontend/pages/list/*`, `frontend/pages/detail/*`, `frontend/pages/notes/*`, `frontend/pages/today-review/*`, `frontend/services/notes.js`, `frontend/tests/pages-browse.test.js`
  - 完成定义（DoD）：
    - 今日待复习空状态显示“今天没有待复习错题”与两个按钮
    - 详情页可触发编辑、删除、恢复入口跳转
    - 自动化用例：`frontend/tests/pages-browse.test.js::test_today_review_empty_state_has_two_actions`
  - 风险 / 注意：页面只做 UI 和本地状态，业务请求经 services 模块

- [ ] T064 [P] 实现 frontend 设置页回收站入口
  - 所属批次：B6
  - 依赖：T057
  - 可并行：是 [P]
  - 涉及文件：`frontend/pages/settings/*`, `frontend/pages/recycle-bin/*`, `frontend/services/mistakes.js`, `frontend/tests/recycle-bin.test.js`
  - 完成定义（DoD）：
    - 设置页展示“回收站”入口
    - 7 天内软删除错题可恢复
    - 自动化用例：`frontend/tests/recycle-bin.test.js::test_recycle_bin_restore_calls_restore_endpoint`
  - 风险 / 注意：恢复只作用于当前用户数据

- [ ] T065 [P] 编写录入到删除恢复全流程手测脚本
  - 所属批次：B6
  - 依赖：T062, T063, T064
  - 可并行：是 [P]
  - 涉及文件：`docs/manual-e2e/001-mvp-ingest-browse-restore.md`, `backend/tests/e2e/test_mvp_smoke.py`
  - 完成定义（DoD）：
    - 手测脚本覆盖录入、标签归并、浏览、删除、恢复
    - e2e smoke 可在 mock OCR/LLM 下运行
    - 自动化用例：`backend/tests/e2e/test_mvp_smoke.py::test_mvp_ingest_browse_delete_restore_smoke`
  - 风险 / 注意：手测不替代自动化测试

## B7 · 收尾与硬化

- [ ] T066 统一错误码枚举与异常映射
  - 所属批次：B7
  - 依赖：T061
  - 可并行：否
  - 涉及文件：`backend/app/errors.py`, `backend/tests/test_errors.py`, `specs/001-mvp-mistake-notes/contracts/openapi.yaml`
  - 完成定义（DoD）：
    - 错误码覆盖 OpenAPI 中全部 `ErrorCode`
    - 内部异常 message 不直接返回前端
    - 自动化用例：`backend/tests/test_errors.py::test_internal_exception_message_is_not_exposed`
  - 风险 / 注意：安全红线，不能泄露内部异常、key、openid

- [ ] T067 实现每用户 ingest 速率限制
  - 所属批次：B7
  - 依赖：T036, T047
  - 可并行：否
  - 涉及文件：`backend/app/services/rate_limit.py`, `backend/app/api/mistakes.py`, `backend/app/api/notes.py`, `backend/tests/test_rate_limit.py`
  - 完成定义（DoD）：
    - 每用户每分钟 ingest 有上限
    - 超限返回稳定错误码
    - 自动化用例：`backend/tests/test_rate_limit.py::test_ingest_rate_limit_is_user_scoped`
  - 风险 / 注意：接触用户数据，必须通过 RLS 双用户隔离测试

- [ ] T068 [P] 实现日志脱敏与敏感字段扫描
  - 所属批次：B7
  - 依赖：T066
  - 可并行：是 [P]
  - 涉及文件：`backend/app/core/logging.py`, `backend/tests/test_logging_redaction.py`, `scripts/check_frontend_secrets.py`, `.pre-commit-config.yaml`
  - 完成定义（DoD）：
    - openid、JWT、API key、AppSecret 不入日志
    - `scripts/check_frontend_secrets.py` 扫描 `frontend/`，阻止 `sk-`、`AKIA`、`ghp_`、高熵疑似密钥
    - gitleaks/pre-commit 可阻止疑似密钥
    - 自动化用例：`backend/tests/test_logging_redaction.py::test_logs_redact_tokens_and_openid`
  - 风险 / 注意：宪法配置与隐私红线

- [ ] T069 [P] 编写 P95 录入时延采样脚本
  - 所属批次：B7
  - 依赖：T037, T044
  - 可并行：是 [P]
  - 涉及文件：`scripts/measure_ingest_latency.py`, `backend/tests/perf/test_ingest_latency_script.py`
  - 完成定义（DoD）：
    - 脚本在 mock OCR/LLM 下输出 P50/P95
    - CI 中只跑轻量 mock 性能 smoke
    - 自动化用例：`backend/tests/perf/test_ingest_latency_script.py::test_latency_script_outputs_p95`
  - 风险 / 注意：不得在 CI 真调外部 OCR/LLM

- [ ] T070 [P] 复核 README、quickstart 与 main 分支保护要求
  - 所属批次：B7
  - 依赖：T005, T065, T068
  - 可并行：是 [P]
  - 涉及文件：`README.md`, `specs/001-mvp-mistake-notes/quickstart.md`, `.github/workflows/ci.yml`, `docs/branch-protection.md`
  - 完成定义（DoD）：
    - README/quickstart 覆盖本地 + 测试环境跑通步骤
    - 文档列明 main 合入必须 ruff、mypy strict、pytest、gitleaks 全绿
    - 自动化用例：`scripts/check_docs.py::test_docs_mention_required_quality_gates`
  - 风险 / 注意：不包含生产部署、域名、备案、购买服务等运营任务

## 依赖图

```text
B1 -> B2 -> B3 -> B4 -> B5 -> B6 -> B7

B4 photo mistake chain blocks:
T027 -> T028 -> T029 -> T030 -> T031 -> T035 -> T036 -> T037
T032 -> T033 -> T039 -> T040 -> T041

B6 browsing chain blocks:
T052 -> T053 -> T054
T055 -> T056 -> T057 -> T058
T059 -> T060 -> T061
```

## 并行执行提示

- B1：T006、T007、T008 可在后端骨架完成后并行推进。
- B2：T013、T014、T015 可与 RLS 测试准备并行，但 B2 结束前必须统一跑迁移和 RLS。
- B3：frontend 的 T025、T026 可在后端 auth route 稳定后并行。
- B4：标签归一化 T032/T033 可与 OCR/LLM client 线并行，最终在 T039 汇合。
- B5：笔记 CRUD 的 T050/T051 可与 PDF 主链测试并行。
- B6：frontend 页面 T062/T063/T064/T065 可在对应后端接口稳定后并行。
- B7：日志、性能脚本、文档复核可并行收尾。

## 风险登记

| 风险 | 影响 | 缓解策略 |
|---|---|---|
| DeepSeek 偶发返回 markdown 代码块包裹 JSON | schema 校验失败、pending 增多 | 在 client 层做容错 strip 后仍走 Pydantic 校验；测试 `test_invalid_json_twice_returns_pending` |
| OCR 对 PDF 切题不稳定 | 候选题目切分错误 | MVP 先规则切分并让用户勾选；复杂切分保留扩展点 |
| service_role 被误用于业务查询 | 跨用户数据泄露 | B2 client 边界测试 + 静态扫描 + RLS 双用户隔离测试 |
| 标签归一化误合并 | 不同知识点被混在一起 | 仅做确定性规则和小型同义词表，不引入向量相似度 |
| signed URL 泄露或过期处理差 | 文件隐私风险或上传失败 | 短 TTL、user_id object namespace、owner-only signed GET 测试 |
| 小程序 401 刷新循环 | 用户请求卡死 | `utils/request.js` 只刷新一次，失败回登录页 |
| 大文件导致 P95 超过 15s | 录入体验下降 | 5MB 图片、10MB/20 页 PDF 限制，超限提示拆分上传 |
| 日志误记录 openid/JWT/key | 隐私与密钥泄露 | 日志脱敏测试 + gitleaks pre-commit + CI |
