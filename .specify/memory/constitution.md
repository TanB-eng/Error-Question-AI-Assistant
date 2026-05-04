<!--
Sync Impact Report
- Version change: N/A -> 1.0.0
- Modified principles: N/A (initial adoption)
- Added sections: Project Identity; Technology Stack; Security and Data Isolation; Backend Engineering Standards; LLM Invocation Standards; Data Model Standards; Mini Program Standards; Testing and Quality Gates; Collaboration and Process Constraints; Non-Goals; Version
- Removed sections: None
- Templates requiring updates:
  - ⚠ pending: .specify/templates/plan-template.md (missing)
  - ⚠ pending: .specify/templates/spec-template.md (missing)
  - ⚠ pending: .specify/templates/tasks-template.md (missing)
  - ⚠ pending: .specify/templates/commands/*.md (missing)
- Retained bracketed literals: [NEEDS CLARIFICATION] and [constitution] are process markers, not template placeholders.
- Follow-up TODOs: Restore or initialize Spec Kit templates so future /specify, /plan, /tasks, and /implement outputs can be checked against this constitution.
-->

# 项目宪法 · 错题与笔记智能辅导小程序

> 本文件是项目的最高约束。`/specify`、`/plan`、`/tasks`、`/implement` 各阶段产物
> 若与本宪法冲突，以本宪法为准。修改本文件需要显式提交，并在 PR 描述中说明原因。

---

## 1. 项目身份

- **产品定位**：面向中学生的错题与笔记数字化管理工具，借助大模型完成自动分类打标、错因分析、复习调度。
- **形态**：微信小程序（C 端）+ FastAPI 后端 + Supabase 数据/鉴权/存储。
- **第一期 MVP 范围**：录入（拍照 / PDF 导入）→ OCR → 大模型自动分类打标 → 用户校对 → 入库 → 按标签浏览。**不做**主动推送、不做相似题生成、不做复习算法调度。

---

## 2. 技术栈（硬约束，不得替换）

| 层 | 选型 | 备注 |
|---|---|---|
| 小程序 | 微信小程序原生（WXML/WXSS/JS） | 不引入 uni-app / Taro / mpvue |
| 后端 | Python 3.11+ / FastAPI / Pydantic v2 | 不引入 Django、Flask |
| 数据库 / 鉴权 / 文件存储 | Supabase（Postgres + Auth + Storage） | 不自建 Postgres、不引入额外鉴权框架 |
| 大模型 | DeepSeek（chat completions，文本模式） | 调用必须走统一 client 封装 |
| OCR | 第三方 OCR（百度云 OCR 或腾讯云 OCR，二选一并固定） | 通过抽象接口接入，便于切换 |
| 包管理 | 后端 `uv` 或 `poetry`（二选一）；小程序原生 npm | |
| 测试 | 后端 pytest；小程序逻辑层用 jest 或最小快照测试 | |

> 任何对上表的偏离，必须在本文件追加 ADR（架构决策记录）后才能生效。

---

## 3. 安全与数据隔离（不可妥协）

1. **所有业务表必须开启 Row Level Security (RLS)**，策略统一为
   `auth.uid() = user_id`，无例外。
2. 后端**禁止使用 Supabase service_role key 直连业务表执行用户级查询**；
   service_role 只允许在以下场景使用：
   - 系统初始化 / 迁移脚本
   - 用户注册时创建 `users` 行
   - 跨用户的统计任务（必须放在独立 `admin` 模块）
3. 普通业务请求一律使用**用户 JWT 走 PostgREST**，由 RLS 兜底数据隔离。
4. 前端**绝不**直接持有 service_role key；小程序只持有用户 access token。
5. 文件上传走 Supabase Storage **signed URL**，由后端签发，bucket 默认 private。
6. 微信 openid、手机号等敏感字段不得写入日志。

---

## 4. 后端工程规范

1. 目录结构强制：
   ```text
   backend/app/
     core/        # 配置、第三方 client（supabase、deepseek、ocr）
     api/         # 路由层，仅做参数解析与调用 service
     services/    # 业务编排，纯函数优先
     schemas/     # Pydantic 模型（请求 / 响应 / 内部 DTO）
     deps.py      # 依赖注入（current_user 等）
   ```
2. **路由层不得直接访问数据库或调用大模型**，必须经 `services/`。
3. **所有接口的请求体与响应体必须使用 Pydantic 模型**，禁止裸 dict 出入参。
4. 错误使用统一 `HTTPException` + 错误码枚举，禁止把内部异常 message 直接抛给前端。
5. 所有外部调用（Supabase、DeepSeek、OCR）必须：
   - 设置超时（默认 30s）
   - 至少一次重试（指数退避）
   - 失败时返回结构化错误，不得静默吞异常
6. 配置一律走环境变量 + Pydantic Settings，禁止硬编码 key。

## 4a. 配置与密钥管理（不可妥协）

  1. **所有密钥、令牌、连接串只能存在于 `.env` 文件中**，包括但不限于：
     - Supabase URL / anon key / service_role key / JWT secret
     - DeepSeek API key / base URL
     - 第三方 OCR 的 secret_id / secret_key / endpoint
     - 微信小程序 AppID / AppSecret
     - 任何第三方服务的 token

  2. **代码、配置文件、文档、注释、提交信息、日志中绝不允许出现真实 key**。
     只能出现"替换名词"——也就是环境变量名本身，例如 `SUPABASE_URL`、
     `DEEPSEEK_API_KEY`、`WECHAT_APP_SECRET`。

  3. **后端**：所有环境变量必须通过 `app/core/settings.py` 中的
     `pydantic_settings.BaseSettings` 子类统一加载，业务代码只能依赖 `settings.xxx`，
     禁止直接 `os.getenv` 散落各处。

  4. **小程序端**：AppID 走 `project.config.json`；任何调用第三方的 secret
     绝不能出现在小程序代码里，必须由后端代理。前端只能拿到由后端签发的
     短期 token（如 Supabase JWT、Storage signed URL）。

  5. **必须提供 `.env.example`**：列出所有需要配置的环境变量名，值留空或写示意
     占位（如 `DEEPSEEK_API_KEY=sk-xxxxxxxx`，明显的假值）。**真实 `.env` 必须
     加入 `.gitignore`，永远不进版本库**。

  6. **CI / 生产环境**通过平台的 secret 管理（GitHub Actions Secrets、服务器
     环境变量、Supabase Edge Functions secrets）注入，禁止把 `.env` 复制到
     生产服务器以外的任何地方。

  7. **泄露处置**：若发现任何 key 已被提交进 git 历史，必须立即吊销并轮换该 key，
     然后再处理 git 历史，顺序不能反。

  8. **代码审查门槛**：PR 中如果出现疑似 key 的字符串（高熵字符串、
     `sk-`/`AKIA`/`ghp_` 前缀等），CI 必须红灯。建议接入 `gitleaks` 或
     `trufflehog` 作为 pre-commit + CI 双重检查。
---

## 5. 大模型调用规范（核心红线）

1. **DeepSeek 输出必须是 JSON**，且必须经过 Pydantic schema 校验后才能进入业务逻辑或落库。校验失败必须重试一次；二次失败则将原始题目入库为“待人工分类”状态，不得丢弃用户数据。
2. Prompt 必须放在 `services/prompts/` 下的独立文件，**禁止散落在业务代码里**，便于版本管理与灰度。
3. 每一次大模型调用必须记录：`prompt 版本号、输入 token、输出 token、耗时、是否命中 schema`，写入 `llm_calls` 审计表。
4. **不得**把用户原始图片直接发送给 DeepSeek（DeepSeek 当前是文本模型）；必须先 OCR 成文本再发送。
5. **不得**信任大模型的分类结果直接落库，必须经过用户在“校对页”确认后才写入 `mistakes` / `tags` 表。
6. 标签归一化：模型给出的 `knowledge_points` 必须先经过同义词归并（如“二次函数顶点式” / “顶点式”），按 `(user_id, subject_id, normalized_name)` upsert 到 `tags` 表，避免标签爆炸。

---

## 6. 数据模型规范

1. 主键统一使用 `uuid`（`gen_random_uuid()`），字典表除外。
2. 所有业务表必含 `user_id uuid not null`、`created_at timestamptz default now()`。
3. 删除一律使用**软删除**（`deleted_at timestamptz`），不允许物理删除用户数据，复习历史除外。
4. 涉及外键的级联策略必须在 migration 中显式声明，不得依赖默认行为。
5. 所有 DDL 变更走 `supabase/migrations/` 下编号 SQL，禁止在 Supabase Studio 里手改生产 schema。

---

## 7. 小程序端规范

1. 网络请求统一走 `utils/request.js`，自动注入 JWT、统一处理 401 刷新。
2. 页面只做 UI 与本地状态，业务请求经 `services/` 模块。
3. 用户上传文件先调后端拿 signed URL，前端 `wx.uploadFile` 直传 Supabase Storage，**不经过后端中转**，节省带宽。
4. 录入流程必须包含**校对页**：AI 识别结果展示给用户，用户可改学科 / 知识点 / 难度 / 题干 / 答案后再保存。
5. 全局禁止 `console.log` 进生产包（构建期检查）。

---

## 8. 测试与质量门槛

1. 后端：service 层目标行覆盖率 ≥ 70%，外部调用必须 mock。
2. 必备集成测试：
   - 微信登录换 JWT
   - 录入端到端（mock OCR + mock DeepSeek）
   - RLS 隔离（双用户互访测试，必须 403/空结果）
3. CI 通过前不得合入 main：lint（ruff）+ 类型检查（mypy strict）+ pytest 全绿。
4. 任何一个 `/implement` 任务完成的标志是：**对应测试通过**，而不是“代码写完了”。

---

## 9. 协作与流程约束

1. 所有功能走 `/specify` → `/plan` → `/tasks` → `/implement` 路径，禁止跳过 spec 直接写代码。
2. spec.md 中的 `[NEEDS CLARIFICATION]` 必须在进入 `/plan` 前清零。
3. 一个 spec 对应一个 feature 分支；分支命名 `NNN-short-slug`（与 `specs/NNN-xxx/` 对齐）。
4. 提交信息使用 Conventional Commits（`feat:` / `fix:` / `chore:` …）。
5. 涉及宪法变更的 PR 标题必须以 `[constitution]` 开头，需要显式人工审阅。

---

## 10. 非目标（明确不做的事）

为了防止 `/plan` 阶段功能蔓延，明确以下事项**第一期不做**：

- 主动推送（订阅消息、模板消息、公众号消息）
- 相似题生成、错因深度解析、知识图谱
- SM-2 / Anki 类间隔复习算法（仅保留 `next_review_at` 字段占位）
- 多端（H5、App、PC Web）
- 班级 / 家长 / 教师视角
- 付费、会员体系
- i18n / 多语言

任何要把以上能力加进 MVP 的提议，必须先修改本宪法的“非目标”清单。

---

## 11. 版本

- v1.0.0 — 2026-05-04 初版，锁定 MVP 范围与技术栈。

---
