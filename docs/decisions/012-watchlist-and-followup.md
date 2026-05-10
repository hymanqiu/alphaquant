# ADR 012: Watchlist and Follow-up Q&A

**状态**: 已采纳
**日期**: 2026-05-01
**影响范围**: watchlist persistence / follow-up LLM endpoint / conversation overlay
**相关代码**: `backend/backend/api/watchlist.py`, `backend/backend/api/follow_up.py`, `frontend/src/context/watchlist-context.tsx`, `frontend/src/components/canvas/follow-up-section.tsx`

## 背景

v0.8 的 collapsed conversation rail 给用户留下了继续提问的入口，v0.9 的 saved thesis 解决了 snapshot 分享，但还缺少留存层：用户想关注 ticker 并在以后重新分析；Pro 用户也想基于当前 canvas 追问，例如"如果增速低 2pp 会怎样"。

v0.10 同时引入 watchlist CRUD 和 follow-up Q&A。

## 考虑的方案

### 方案 A: Watchlist 点击打开历史快照

- 类似 saved theses。
- 问题：用户点 watchlist ticker 的直觉是看最新状态，不是看保存时状态。

### 方案 B: Follow-up 在前端本地生成

- 不消耗 LLM 预算。
- 问题：前端没有可靠的 grounded reasoning 能力，无法复用已有 prompt / schema / budget guard。

### 方案 C: Watchlist 点击触发重分析 + `/api/follow-up` Pro LLM endpoint ✓

- Watchlist 表示关注未来状态。
- Follow-up 复用后端 LLMClient、prompt 库、预算和计费。
- Pro gate 与其他 LLM-heavy 功能一致。

## 决策

采用方案 C。

Watchlist schema：

```text
watchlist_items
id                  integer primary key
user_id             FK users.id on delete cascade
ticker              string(8)
target_mos_pct      float | null
created_at          timestamptz
updated_at          timestamptz
last_checked_at     timestamptz | null
last_mos_pct        float | null
last_signal         string | null
UNIQUE (user_id, ticker)
```

API 表面：

- `GET /api/watchlist`: auth required，返回 `{items}`
- `PUT /api/watchlist/{ticker}`: auth required，按 `user_id+ticker` upsert，`target_mos_pct` 范围 `[-100, 100]`
- `DELETE /api/watchlist/{ticker}`: auth required，204
- `POST /api/follow-up`: `require_pro`，body `{ticker, question, hero_snapshot?, components_snapshot[]}`，返回 `{answer, tab_hint, confidence}`

Follow-up 请求流程：

1. `require_pro` 认证和 tier gate
2. 复用 `BUCKET_RECALCULATE` rate limit
3. `bind_client_ip` 让 LLM accounting 归属请求 IP
4. `_hero_summary` + `_components_summary` 渲染当前 canvas context，components 最多内联 12 张
5. `complete_json("follow_up", version=1, response_model=FollowUpAnswer)`
6. 前端验证 `tab_hint` 后展示 "See Valuation tab" 等跳转按钮

`activeTab` 从 `AnalysisCanvas` 提升到 `AppShell`，让 `ConversationPanel` 的 follow-up answer 可以跳转 canvas tab。`FollowUpSection key={ticker}` 保证 ticker 切换时 thread 和 input 状态重置。

Saved thesis 和 watchlist contexts 使用 `AbortController` 管理 in-flight refresh，logout 或重复 refresh 时 abort 旧请求，并在 await 后检查 `signal.aborted`，避免旧 auth 响应覆盖 logout 后的空列表。

## 后果

**正面**:

- Watchlist 语义清晰：关注 ticker 最新分析，而不是历史快照。
- Follow-up 与 Pro LLM 节点使用同一套 gate、budget、prompt schema。
- `hasPending` 防止 Enter 连按造成双提交和 thread index 竞态。
- `tab_hint` 把回答直接连接到 supporting tab。

**负面**:

- Follow-up 的 prompt context 来自当前客户端 canvas payload，需要持续做输入清理和大小限制。
- Watchlist 的 `last_checked_at / last_mos_pct / last_signal` 只是 schema 占位，cron 告警尚未实现。
- Follow-up 与 DCF recalc 共用 rate-limit bucket，重度使用时两者会互相影响。

**缓解措施**:

- Free 用户对 `/api/follow-up` 得到明确 403 upgrade path。
- 前端对 watch threshold 做 `[-100, 100]` 范围检查，避免 422 被静默吞掉。
- Follow-up question 已经过 `sanitize_text` 包裹；snapshot summary 的统一清理作为后续 hardening。
