# Research: 错题与笔记智能辅导 MVP

**Date**: 2026-05-04  
**Spec**: `specs/001-mvp-mistake-notes/spec.md`

## Decisions

### OCR Provider

**Decision**: 本期默认实现锁定腾讯云 OCR，通过 `OCRClient` 抽象接口接入。

**Rationale**:

- 中文图片、试卷、通用印刷体识别能力成熟，适合中学试卷和手写批注混合场景的 MVP。
- 与微信生态同属腾讯云体系，账号、备案、资源管理和后续小程序云资源协作更顺。
- 官方 SDK 与 HTTP API 都可封装在 `backend/app/core/ocr_client.py`，不污染业务服务。
- 支持保留百度云 OCR 作为替换实现，只需实现相同接口，不影响 `services/ocr.py`。

**Alternatives considered**:

| Provider | Status | Reason |
|---|---|---|
| 腾讯云 OCR | 采纳 | 中文教育材料场景适配好，微信生态协同成本低 |
| 百度云 OCR | 修改后保留为备选 | 中文 OCR 能力强，但本期不同时维护两套默认实现 |
| 自建 OCR | 拒绝 | 违反“第三方 OCR 二选一并固定”的宪法约束，且 MVP 成本过高 |

### PDF Processing

**Decision**: PDF 限制为单文件最大 10MB、最多 20 页；OCR 后做规则切分并返回候选。

**Rationale**:

- 与澄清结果一致，控制处理耗时和校对负担。
- 候选展示让用户勾选错题，避免自动切分错误直接落库。
- 大型 PDF 提示拆分上传，保持 MVP 简洁。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| 10MB / 20 页 | 采纳 | 用户已确认；适合 MVP |
| 20MB / 30 题 | 拒绝 | 用户选择了更严格限制 |
| 异步大文件处理 | 拒绝 | 超出 MVP，不利于 15s 体验目标 |

### Photo Multi-Question Handling

**Decision**: 每张照片只支持一道题；检测到明显多题时提示裁剪或重拍。

**Rationale**:

- 与澄清结果一致。
- 降低切题、校对、标签归属复杂度。
- PDF 导入已经覆盖多题批量录入。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| 一图一题 | 采纳 | 简化 MVP 且更可靠 |
| 自动多题切分 | 拒绝 | 容易引入识别错误和复杂校对 |
| 手动框选多题 | 拒绝 | 交互成本高，不符合 8 步内首题目标 |

### Subject Selection

**Decision**: 用户上传前必须选择学科，未选择时提示先选择；校对页仍允许修改。

**Rationale**:

- 与澄清结果一致。
- 减少模型误判学科带来的标签污染。
- 校对页修改能力保留容错。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| 上传前必选学科 | 采纳 | 用户已确认；标签归一化更稳定 |
| OCR/LLM 推断学科 | 拒绝 | 容易错误归类 |
| 可选学科 + 自动推断 | 拒绝 | 规则更复杂，MVP 不需要 |

### LLM JSON Validation

**Decision**: DeepSeek 输出必须按 `ClassifyResult` Pydantic 模型校验；失败重试一次；二次失败返回 pending 分支并写 `llm_calls`。

**Rationale**:

- 直接来自宪法红线。
- 保证模型输出不能绕过校对进入最终业务表。
- pending 降级保证用户数据不丢失。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| Pydantic schema + retry once | 采纳 | 宪法要求且实现清晰 |
| 信任模型 JSON | 拒绝 | 违反宪法，风险高 |
| 无限重试 | 拒绝 | 影响延迟和成本 |

### Tag Normalization

**Decision**: 使用确定性规范化 + 小型同义词映射 + 唯一索引，不引入向量相似度。

**Rationale**:

- 满足“同义知识点归并”验收标准。
- 对 MVP 可测试、可解释。
- 唯一索引从数据层阻止标签爆炸。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| 确定性规则 + normalized_name | 采纳 | 简单可测，符合宪法 |
| 向量相似度归并 | 拒绝 | 超出 MVP，可能误合并 |
| 纯用户手动合并 | 拒绝 | 增加学生负担 |

### Auth Session

**Decision**: 微信 `wx.login` code 由后端换 openid；后端只在用户创建/绑定时使用 Supabase admin 能力；后续请求全部使用用户 JWT。

**Rationale**:

- 与宪法 service_role 限制一致。
- RLS 成为最终数据隔离边界。
- 小程序只保存 access token / refresh token，不接触 service_role。

**Alternatives considered**:

| Option | Status | Reason |
|---|---|---|
| 后端换 openid + Supabase JWT | 采纳 | 满足微信登录和 RLS |
| 小程序直连 service_role | 拒绝 | 严重违反宪法 |
| 自建鉴权 | 拒绝 | 宪法锁定 Supabase Auth |

## Reference Plan Disposition

User-provided reference path:
`C:\Users\Administrator\.claude\plans\wise-coalescing-reef.md`

**Status**: 无法采纳。该路径在当前机器上不可读，读取结果为文件不存在。

| Reference area requested | Disposition | Reason |
|---|---|---|
| 数据模型 | 拒绝直接采纳 | 参考文件不可读；本计划基于 spec 与宪法重新生成 |
| 接口划分 | 拒绝直接采纳 | 参考文件不可读；接口按用户本次输入的端点清单输出 |
| 关键流程 | 修改后采用用户输入 | 用户本次输入已给出 A/B/C 流程，优先级高于外部草稿 |
| OCR 候选 | 采纳用户要求并补充决策 | research 中完成腾讯云/百度云对比并锁定腾讯云 |

如后续补回参考草稿，可单独运行一次 review/analyze 对比差异；当前不阻塞计划产出。

## Third-Party Dependencies

### Backend Runtime

| Dependency | Purpose |
|---|---|
| fastapi | HTTP API framework |
| uvicorn | Local ASGI server |
| pydantic v2 | request/response/internal schemas |
| pydantic-settings | environment-driven settings |
| httpx | outbound HTTP to DeepSeek, WeChat, Tencent OCR, Supabase REST if needed |
| tenacity | exponential backoff retry |
| python-jose or pyjwt | Supabase JWT verification |
| supabase-py or postgrest client | Supabase Auth/PostgREST/Storage integration |
| python-multipart | upload/signing request compatibility if needed |

### Backend Dev/Test

| Dependency | Purpose |
|---|---|
| pytest | test runner |
| pytest-asyncio | async service tests |
| httpx | API integration tests |
| respx | mock outbound HTTP |
| ruff | lint |
| mypy | strict type check |
| coverage | coverage reporting |

### Frontend

| Dependency | Purpose |
|---|---|
| native npm tooling | package management for frontend utilities/tests |
| jest or minimal snapshot test runner | logic/component sanity tests |

### External Services

| Service | Purpose | Notes |
|---|---|---|
| WeChat Login API | exchange `code` for `openid` | do not log openid |
| Supabase Auth | user identity/JWT | service_role only for bootstrap |
| Supabase Postgres | business data | RLS required |
| Supabase Storage | private original files | signed PUT URL upload |
| DeepSeek Chat Completions | text classification | JSON output only |
| Tencent Cloud OCR | OCR | default implementation behind abstraction |

## Open Items Deferred to Planning/Implementation

- Image compression strategy: choose deterministic client-side compression thresholds while preserving OCR quality. It does not change business scope and can be finalized during implementation planning.
- Exact OCR PDF segmentation heuristics: define in tasks/tests after Tencent OCR response shape is integrated.
