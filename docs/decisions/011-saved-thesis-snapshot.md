# ADR 011: Saved Thesis Snapshot

**状态**: 已采纳
**日期**: 2026-05-01
**影响范围**: saved thesis persistence / public share view / sidebar retention
**相关代码**: `backend/backend/api/saved_thesis.py`, `backend/backend/services/saved_thesis.py`, `frontend/src/context/saved-thesis-context.tsx`, `frontend/src/app/s/[id]/page.tsx`

## 背景

分析完成后，用户需要把当前 thesis 固定下来，之后回访时比较关键字段是否变化，并能把静态结果分享给非登录用户。重新跑分析无法表达"当时看到的判断"，所以需要保存 immutable snapshot。

## 考虑的方案

### 方案 A: 只保存 ticker，打开时重新分析

- 存储最小。
- 问题：不是 snapshot，无法比较当时的 MoS、confidence、price、signal。
- 问题：分享链接依赖实时数据和外部 API，可重复性差。

### 方案 B: 将每张卡片规范化为多张关系表

- 查询能力强。
- 问题：当前产品主要是保存和重放完整 canvas，规范化收益小。
- 问题：卡片 schema 会快速演进，关系表迁移成本高。

### 方案 C: UUID 主键 + JSONB hero/components snapshot ✓

- 保存完整渲染输入。
- schema 对前端组件演进更宽容。
- public share URL 不可遍历。

## 决策

采用方案 C。

`saved_theses` 结构：

```text
id                  uuid v4 string, primary key
user_id             FK users.id on delete cascade
ticker              string(8)
title               string(200) | null
is_public           boolean default true
hero_snapshot       JSONB
components_snapshot JSONB
created_at          timestamptz
```

API 表面：

- `POST /api/saved-thesis`: auth required，保存 `ticker / title? / is_public? / hero_snapshot / components_snapshot`
- `GET /api/saved-thesis`: auth required，返回 summary list，不带完整 components
- `GET /api/saved-thesis/{id}`: owner only
- `DELETE /api/saved-thesis/{id}`: owner only
- `GET /api/share/thesis/{id}`: unauthenticated，仅 `is_public=true` 返回

Frontend 使用 `SavedThesisProvider` 管理列表和乐观 UI。`HeroActions` 中 [Save] 成功后切换为 [Saved] / [Share]；`/s/[id]` 读取 public thesis 并渲染只读 canvas。

`VerdictHero` 接收 `isSnapshotView`，在 public snapshot 页面隐藏 Save/Watch 和 diff strip，避免把访问者自己的 saved thesis 与别人分享的历史 snapshot 做无意义比较。

## 后果

**正面**:

- Snapshot 可重复渲染，不依赖重新分析。
- UUID v4 share URL 非可遍历。
- JSONB 保存完整 `ComponentInstruction[]`，前端无需额外转换。
- `is_public` 默认 true，匹配"保存并分享"的主要使用场景。

**负面**:

- JSONB 不适合复杂跨 thesis 查询。
- 保存 payload 大小需要后续持续约束，避免 storage abuse。
- 私有 saved row 当前不提供 share 导航，UI 上仍有后续空间。

**缓解措施**:

- 列表 endpoint 返回 summary，不读取完整 components。
- Public endpoint 只返回 `is_public=true`。
- 创建请求对 title、ticker、component count、hero key count 和 component id/type 做 Pydantic 限制；总 JSON byte/depth 限制作为后续 hardening。
