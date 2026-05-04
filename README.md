# 错题与笔记智能辅导小程序

面向中学生的错题与笔记数字化管理 MVP。第一期聚焦微信登录、拍照/PDF 录入、OCR、AI 结构化建议、用户校对、标签浏览、软删除恢复与今日待复习占位。

## 项目结构

```text
backend/     FastAPI 后端
frontend/    微信小程序原生前端
supabase/    Supabase migrations
specs/       Spec Kit 规格、计划和任务
```

## 开发入口

- 规格：[specs/001-mvp-mistake-notes/spec.md](specs/001-mvp-mistake-notes/spec.md)
- 实施方案：[specs/001-mvp-mistake-notes/plan.md](specs/001-mvp-mistake-notes/plan.md)
- 快速开始：[specs/001-mvp-mistake-notes/quickstart.md](specs/001-mvp-mistake-notes/quickstart.md)
- 任务清单：[specs/001-mvp-mistake-notes/tasks.md](specs/001-mvp-mistake-notes/tasks.md)

## 质量门槛

main 合入前必须通过：

- `ruff`
- `mypy strict`
- `pytest`
- `gitleaks`

真实 `.env`、JWT、API key、AppSecret、service_role key 永远不得提交。
