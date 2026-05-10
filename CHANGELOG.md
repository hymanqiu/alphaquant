# AlphaQuant 更新日志

本文件记录项目的所有重要变更。文档体系导航请参阅 `ARCHITECTURE.md`。

## 版本总览

| 版本 | 日期 | 类型 | 变更摘要 |
|------|------|------|----------|
| v0.11.0 | 2026-05-06 | feat | **Pulse Tab — 技术指标 + 大盘 + 情绪看板（13 节点）**：新增第 13 节点 `technical_pulse`（无 LLM、Free 可用），位于 `strategy → technical_pulse → qualitative_analysis`。后端：`technical_pulse_math.py` 11 条规则（8 bull / 3 bear）+ 加权 tanh 评分 0-100，`technicals_data.py` 并发 async 拉 FMP 1Y OHLCV + ^VIX / ^TNX / ^DXY / 板块 ETF + Finnhub insider 90d + CNN F&G（asyncio.gather，冷启动 ~2s → ~400ms），所有 fetcher 套 5 min TTL+LRU 内存缓存（maxsize=256，市场指数同 IP 多次分析共享，FMP 调用 7→0 / 7→3）。前端新 `pulse/` 目录 6 张卡（hero / 1Y K 线 lightweight-charts v5 + MA20 + volume / 4-up 指标网格 / signal chips / 5 项 market context / F&G 半圆渐变仪表盘 + sentiment 列表）。新 `pulse` tab 插入 Risks 与 Sources 之间。`follow_up_v2.yaml` 把 `pulse` 加进 `tab_hint` 严格枚举。`use-analysis-stream.ts::PIPELINE_NODES` 同步加 `technical_pulse`（前端进度条原本硬编码 12 步）。`^TNX` 自适应缩放（CBOE × 10 与 FMP 归一化两种 provider 行为通吃）。验收：150 backend tests / tsc 无新增错误 / Pulse 节点 0 LLM 调用。详见 [ADR 013](docs/decisions/013-pulse-tab.md)。 |
| v0.10.0 | 2026-05-01 | feat | **Watchlist + Follow-up Q&A（Phase 3）**：新 `WatchlistItem` ORM（user_id+ticker 唯一约束，`target_mos_pct` 阈值占位）+ `/api/watchlist` CRUD（cron 告警留待后续）。Hero 加 [Watch] 按钮 + 阈值对话框（[-100, 100] 客户端验证）；sidebar 加 "Watching" 段落，点击 ticker 触发重分析。新 `/api/follow-up` 端点（Pro 必需）+ `follow_up_v1.yaml` prompt：基于当前 hero+canvas 的上下文回答 Q&A，复用现有 LLM 客户端 + 预算守护 + 计费。`<FollowUpSection>` 嵌入对话面板 overlay，threaded Q&A，pending 期间禁止双提交，`tab_hint` 答案带可点击的 tab 跳转。Context value memoize + AbortController 修 logout 期 in-flight 竞态。详见 [ADR 012](docs/decisions/012-watchlist-and-followup.md)。 |
| v0.9.0 | 2026-05-01 | feat | **Save Thesis + Share Link（Phase 2）**：新 `SavedThesis` ORM（UUID 主键 + JSONB hero/components 快照 + `is_public` 默认 true）+ `/api/saved-thesis` CRUD + 公开 `/api/share/thesis/{id}` 无授权读取。Hero 新增 [Save] / [Share] 按钮（Pro 启用），sidebar 加 "Saved theses" 段落，重访同一 ticker 时 Hero 下方显示 MoS / Confidence / Price / Signal 的差异条。`/s/[id]` 公开只读 canvas（隐藏 Save/Watch + 不显示 diff strip）。详见 [ADR 011](docs/decisions/011-saved-thesis-snapshot.md)。 |
| v0.8.0 | 2026-05-01 | feat | **Verdict-First UI 重构（Phase 1）**：右侧 19 张卡片纵向堆叠 → sticky **Verdict Hero**（signal/MoS/confidence/risks/thesis/entry-exit 5 字段）+ **5 个 Tab**（Verdict / Valuation / Strategy / Risks & Moat / Sources）。`ConversationPanel` 在 `status==='complete'` 后自动折叠为 **56px rail**，点击展开 420px overlay。推理 trace 从 chat 移至 Sources tab。Tab 不自动切换，新卡片用脉冲点提示。详见 [ADR 010](docs/decisions/010-verdict-first-ui.md)。 |
| v0.7.2 | 2026-04-28 | feat | **Admin 运行时切换 LLM provider**：`PATCH /api/admin/settings` 现支持 `llm_api_key` / `llm_base_url` / `llm_model` / `llm_narrative_*` 6 个字段。改动后 LLMClient singleton 自动失效，下次请求重建（不重启）。GET/PATCH/reset 响应中 api_key 自动 redacted（`***last4` 格式）。bad URL 拒绝在 PATCH 阶段，避免后续请求才发现 |
| v0.7.1 | 2026-04-26 | docs | **文档体系重构（@Skyward666 + follow-up）**：ARCHITECTURE.md 拆分为三层文档体系（系统全景 + `docs/nodes/` 节点详情 + `docs/decisions/` 架构决策记录）。__PR #3__ 引入结构 + 8 个 v0.4 节点文档 + 5 个 ADR。__PR #6__ 跟进补齐 v0.5/0.6/0.7 内容：4 个 Pro 节点文档（09-12）+ 4 个 ADR（006-009）；ARCHITECTURE.md §11-14 缩为 §10 概览（-320 行）|
| v0.7.0 | 2026-04-25 | feat | **认证 + 订阅分级（Phase 2）**：邮箱/密码 + Magic Link + Google OAuth 三种登录方式；PostgreSQL 持久化；JWT 会话；4 个 Pro 节点按 user.tier 门控（free 用户看到锁定预览卡）；admin 可手动升级用户为 Pro。新增 `services/auth/` 模块、Alembic 迁移、AuthProvider Context、登录/注册页 |
| v0.6.0 | 2026-04-25 | feat | **5 个 LLM Pro 节点（Phase 3）**：投资论点生成器、10-K MD&A 定性分析、10-K Risk Factors 抽取、10-K YoY 风险变化对比、Hamilton Helmer 7 Powers 护城河评分。统一逐字引文核验防幻觉；分析管线从 8 节点扩至 12 节点 |
| v0.5.0 | 2026-04-24 | feat | **LLM 基础设施 + 成本围栏（Phase 1）**：统一 LLMClient + Prompt YAML 库 + Provider 抽象 + Token 计费；BudgetGate（全局/per-IP 双闸熔断）+ IP 限流 + RuntimeSettings（admin 可热改阈值）+ `/api/admin/*` 接口（usage / settings / settings/reset） |
| v0.4.0 | 2026-04-22 | feat | 事件影响分析：两步 LLM 筛选重大新闻 → 自动调整 DCF 参数 → 重算内在价值。改进新闻获取（7天分批、公司名匹配、权威来源白名单、SEC 8-K 整合） |
| v0.3.0 | 2026-04-21 | feat | 消息面情绪修正：Finnhub 新闻 + 内部人情绪 → 综合评分 → 安全边际调整。新增 Finnhub 客户端、DeepSeek LLM 情绪分析、sentiment_card 组件 |
| v0.2.0 | 2026-04-17 | feat | 相对估值（市场乘数法）：当前乘数 + 历史百分位 + 同业对比。新增 FMP API 客户端、relative_valuation_card 组件 |
| v0.1.0 | 2026-04-17 | — | 初始版本：SEC EDGAR 数据获取、财务健康扫描、DCF 估值建模、买入策略、数据溯源、SSE + Generative UI |

---

## v0.11.0 — Pulse Tab：技术指标 + 大盘 + 情绪看板

**日期：** 2026-05-06

### 概要

填补 Free / Pro 之间的产品差距：技术面 + 大盘 + 情绪面快照对所有用户开放，全程 0 LLM 调用，全局预算耗尽时仍可用。新增第 13 节点 `technical_pulse`，前端新增 6 张卡组成的 `pulse` tab（在 Risks 与 Sources 之间）。详见 [ADR 013](docs/decisions/013-pulse-tab.md)。

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/technical_pulse.py` | 第 13 节点主体（含 I/O，串行 async）。FMP key 缺失 / OHLCV < 50 bars / 任意异常 → return `pulse_result=None`，`ErrorEvent(recoverable=True)`，下游 Pro 节点不受影响 |
| `backend/backend/agents/nodes/technical_pulse_math.py` | 纯函数：SMA/EMA/RSI/MACD/VWAP 5 indicator + 11 detector（8 bull + 3 bear）+ `composite_score()` 加权 tanh 0-100 评分 + 4 张 indicator card builder |
| `backend/backend/services/technicals_data.py` | FMP `/stable/historical-price-eod/full` + `/stable/quote` + Finnhub `/stock/insider-transactions` + CNN `production.dataviz.cnn.io/index/fearandgreed/graphdata`（browser UA）+ `_SECTOR_ETF` SPDR 11 项映射（FMP profile.sector → XLK/XLF/...）。**4 个 fetcher 套 `@_cached(ttl=300s)` 装饰器**：按非 httpx 客户端 args 为 key、失败结果（None/空 list/`(None, None)`）不缓存让下次重试；同 IP 5 min 内重复分析时 SPY/VIX/TNX/DXY/sector ETF/F&G 全命中 → FMP 调用 7→0（同 ticker）或 7→3（不同 ticker） |
| `backend/backend/models/technicals.py` | 6 个 Pydantic 数据契约（OHLCV / TechnicalIndicator / TechnicalSignal / MarketContext / SentimentSignals / TechnicalPulse） |
| `backend/backend/prompts/follow_up_v2.yaml` | bump 自 v1：`tab_hint` 严格枚举里加 `"pulse"` + system prompt 给 LLM 路由提示（"Use 'pulse' for technical indicators / signals / sentiment 等"）。v1 保留 |
| `backend/tests/agents/nodes/test_technical_pulse_math.py` | 17 个单测覆盖评分阈值、5 个关键 detector（golden cross / MACD 5d 窗口 / RSI bearish divergence / distribution days ≥4 / above_vwap 5 连日 / relative strength vs SPY） |
| `docs/nodes/13-technical-pulse.md` | 节点合同文档 |
| `docs/decisions/013-pulse-tab.md` | ADR：决策摘要 + 11 条规则全表 + 视觉规范 + 降级策略 + 验收清单 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/models/agent_state.py` | 加 `pulse_result: dict[str, Any] \| None` |
| `backend/backend/agents/value_analyst.py` | import + `add_node("technical_pulse", ...)` + 重接边 `strategy → technical_pulse → qualitative_analysis`，docstring 节点链更新 |
| `backend/backend/api/follow_up.py` | `complete_json(prompt_name="follow_up", version=2, ...)`（v1 → v2）|

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/pulse/pulse-score-hero.tsx` | 浅色主题 Card：`text-[44px]` mono 评分 + tone-colored badge（bull=emerald / bear=rose / neutral=amber）+ 力量条（`% bullish weight`）|
| `frontend/src/components/pulse/price-chart-card.tsx` | shadcn Card 外壳，`next/dynamic` + `{ ssr: false }` 加载 impl |
| `frontend/src/components/pulse/price-chart-impl.tsx` | lightweight-charts v5：`addSeries(CandlestickSeries / LineSeries / HistogramSeries)`，3M/6M/1Y 切换仅调 `setVisibleRange()` 不重建图，theme detect 一次（depth 检 `<html.dark>`），unmount 时 `chart.remove()` 防泄漏 |
| `frontend/src/components/pulse/indicator-grid-card.tsx` | `grid-cols-2 sm:grid-cols-4`：RSI 14 / MACD hist / MA stack / 52W position 四张 tile，长 value（"20 > 50 > 200"）自动缩到 `text-[16px]` |
| `frontend/src/components/pulse/signal-chips-card.tsx` | bull 优先 + 组内 weight 降序，pill chip + 原生 `title` tooltip + `animate-in fade-in slide-in-from-bottom-1` 每 chip 40ms stagger（无 framer-motion）|
| `frontend/src/components/pulse/market-context-card.tsx` | `grid-cols-2 sm:grid-cols-5` 五项 tile：SPY / VIX / 10Y / DXY / 板块 ETF。change_pct 按符号着色（涨绿跌红）；绝对值（VIX/10Y/DXY）中性；任一缺失 → "—" |
| `frontend/src/components/pulse/sentiment-pulse-card.tsx` | SVG 半圆 F&G gauge：viewBox 200×130，半径 80，多色 linearGradient（rose-500 → amber-500 → emerald-500），spring 入场动画（`useEffect + requestAnimationFrame` + cubic-bezier(0.34, 1.56, 0.64, 1)），指针端点 `feGaussianBlur` glow，theme 适配（`stroke-foreground`）。右半 4 行 sentiment metrics |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/canvas/tab-groups.ts` | `TabId` 加 `"pulse"`，`TAB_ORDER` 插入 `verdict, valuation, strategy, risks, pulse, sources`，`TAB_BY_TYPE` 加 6 个 `pulse_*` 映射，`groupByTab` 初始 record 加 `pulse: []` |
| `frontend/src/components/canvas/canvas-tabs.tsx` | `seenCounts` 初始化加 `pulse: groups.pulse.length` |
| `frontend/src/components/component-registry.ts` | 注册 6 个 pulse 组件的 `lazy(() => import("./pulse/..."))` |
| `frontend/src/hooks/use-analysis-stream.ts` | `PIPELINE_NODES` 加 `technical_pulse`（位置在 `strategy` 之后，跟后端 graph 同序）。这是 task progress 进度条的真相源——硬编码 12 步会导致新节点的 step_complete 事件被忽略、进度条停滞 |
| `frontend/package.json` | 加 `lightweight-charts@^5` 依赖 |
| `frontend/AGENTS.md` | 加 lightweight-charts ssr:false 注意事项 |

### 关键设计

- **0 LLM 调用**：纯规则。全局 LLM 预算耗尽 / `AQ_LLM_API_KEY` 为空时 Pulse tab 仍可用——这是本节点最大工程优势
- **节点位置**：`strategy` 之后、`qualitative_analysis`（Pro）之前。Pro 节点失败不影响 Pulse、Pulse 失败不影响 Pro
- **Free 可用，预留 Pro 钩子**：v1 不实现 `pulse_score_explainer_locked_card` / `insider_detail_locked_card`（ADR §4.8）
- **视觉一致性**：浅色主题主导，配色用 emerald / rose / amber（与 strategy_dashboard / risk_factors_card 同色系），不强制深色 + neon
- **`^TNX` 自适应**：值 > 20 才 ÷10——同时覆盖 CBOE 原生（yield × 10）与 FMP 归一化两种 provider 行为
- **3M/6M/1Y 切换零网络**：单次 setData 全 1Y 数据，切换只调 `setVisibleRange()`
- **TTL 缓存挡 FMP 限流**：免费档每天 250 calls 易耗。`@_cached(ttl=300s)` 装饰器按非 httpx-client args 建 key，市场指数（SPY history / VIX / TNX / DXY / SPDR sector ETF / CNN F&G）全 IP 共享；失败值不缓存让下一次重试。一个交互测试 session 内 FMP 调用从每分析 7 次降到 0-3 次
- **lightweight-charts v5 与 Next.js 16 协作**：必须 `dynamic + ssr:false`（库 import 即触 `window`），见 `frontend/AGENTS.md`

### 已知未做

- **AAII bull-bear 数据**：v1 返回 None（待注册账号），sentiment_pulse_card 该行显示 "—"
- **Pulse 数据不进 saved_theses**：每次重新计算（无缓存）
- **K 线主题切换不实时**：mount 时一次性 detect `<html.dark>` 设色；用户切换主题需刷新页面（避免装 MutationObserver）
- **行业横向比较** / **用户自定义信号权重** / **WebSocket 实时推送**：全部留待 v0.12+

### 验证

- `pytest -q` → **150 passed**（17 新 + 133 旧无回归）
- `pytest -q tests/agents/nodes/test_technical_pulse_math.py` → 17 passed
- `npx tsc --noEmit` → 5 个预存 recharts 类型错误（fcf-chart / revenue-chart）与 Pulse 无关
- `/api/admin/usage` 24h 内 task tags 不含 `pulse` / `technical_pulse` → 节点全程未触 LLM client

---

## v0.10.0 — Watchlist + Follow-up Q&A（Phase 3）

**日期：** 2026-05-01

### 概要

留存层闭环：把 ticker 加入 watchlist 设阈值（cron + 邮件告警留待后续），现 schema 已就绪；Pro 用户在 overlay conversation 里直接对当前 canvas 上下文提问（"如果增速 -2pp 会怎样"），LLM 答案带 tab_hint 直接跳到相关 tab。Phase 1 的折叠 rail 现在有了真正的"Ask follow-up"含义。

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/api/watchlist.py` | 3 个端点：GET `/api/watchlist`（列表 mine）/ PUT `/api/watchlist/{ticker}`（upsert 含 `target_mos_pct: ge=-100, le=100`）/ DELETE `/api/watchlist/{ticker}`。Ticker `^[A-Za-z]{1,8}$` 验证 |
| `backend/backend/api/follow_up.py` | POST `/api/follow-up`（`require_pro` gate + BUCKET_RECALCULATE 限流 + `bind_client_ip` 计费）。请求 body `{ticker, question(2-500 chars), hero_snapshot?, components_snapshot[]}`；调用 `complete_json("follow_up", v=1, response_model=FollowUpAnswer)` 并返回 `{answer, tab_hint, confidence}` |
| `backend/backend/prompts/follow_up_v1.yaml` | YAML prompt（temp=0.4, max_tokens=1200）。System prompt 含反注入边界（`<<<USER_CONTENT>>>` 标记 + DATA-only 指令）。Schema 强制 tab_hint ∈ verdict/valuation/strategy/risks/sources/null |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/main.py` | 加 `watchlist_router` + `follow_up_router` 注册 |

> v0.9 已添加 `services/watchlist.py`（schema 就绪）；本版本启用其 code path。

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/lib/watchlist-api.ts` | listWatchlist (signal) / upsertWatch / removeWatch |
| `frontend/src/lib/follow-up-api.ts` | askFollowUp |
| `frontend/src/context/watchlist-context.tsx` | `WatchlistProvider`：refresh / add（先 filter 再 prepend，处理同 ticker 改阈值）/ remove / `isWatching` / `itemFor`。useMemo value 防全量 consumer re-render；AbortController + post-await aborted 检查防 logout 竞态 |
| `frontend/src/components/canvas/follow-up-section.tsx` | 嵌入对话面板（仅 `status==='complete' && components.length > 0` 时渲染）。Threaded Q&A，pending 期间 `submittable=false` 禁止双提交。Pro-only gate；非 Pro / anonymous 显示 disabled input + 升级提示。`tab_hint` 答案显示 "See Valuation tab →" 可点击 button |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/lib/types.ts` | 加 `WatchlistItem` / `TabHint` / `FollowUpAnswer` 类型 |
| `frontend/src/context/saved-thesis-context.tsx` | 同 watchlist 一样加 useMemo value + AbortController 模式 |
| `frontend/src/components/canvas/hero-actions.tsx` | 加 `<WatchButton>` + `<ThresholdDialog>`。Watch 按钮 toggle：未 watch 时打开阈值对话框；已 watch 时点击 unwatch（"已 watching 时点=改阈值"是 future polish）。ThresholdDialog 客户端 [-100, 100] 验证 + 范围错误红框 + disable 提交，避免 422 静默吞掉 |
| `frontend/src/components/conversation-panel.tsx` | 接收 `components?` + `onJumpToTab?` props；在 verdict 下方条件性渲染 `<FollowUpSection key={ticker}>`（`key={ticker}` 防缓存切换 thread 残留） |
| `frontend/src/components/analysis-canvas.tsx` | activeTab 提升为 prop（来自 app-shell），不再内部 `useState`。VerdictHero `onJumpToTab` 走父级 setter |
| `frontend/src/components/layout/app-shell.tsx` | 把 `activeTab` 状态提升至此层（让 conversation overlay 的 follow-up tab_hint 能切 canvas tab）+ `handleJumpToTab` useCallback 同时关闭 overlay |
| `frontend/src/components/layout/sidebar.tsx` | 加 `<WatchlistSection>`：列出 user 的 watchlist，点 ticker 合成 fake history entry 触发 `onSelectHistory` 走 `handleSubmitTicker` 重分析 |
| `frontend/src/app/layout.tsx` | 包 `<WatchlistProvider>` |

### 数据库 schema

```sql
watchlist_items (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ticker          VARCHAR(8) NOT NULL,
  target_mos_pct  FLOAT,                          -- alert threshold（cron 待补）
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_checked_at TIMESTAMPTZ,                    -- ↓ cron 字段，目前由 schema 占位
  last_mos_pct    FLOAT,
  last_signal     VARCHAR(32),
  UNIQUE (user_id, ticker)
)
```

> 表已在 v0.9 alembic 0002 迁移中创建；本版本启用 code path。

### Follow-up Q&A 数据流

```
ConversationPanel overlay (status==='complete')
  └ <FollowUpSection key={ticker}>
       │
       ├─ user types Q
       ├─ submit → askFollowUp({ticker, question, hero_snapshot, components_snapshot})
       │         POST /api/follow-up (require_pro, BUCKET_RECALCULATE limit, bind_client_ip)
       │
       │   backend:
       │     hero_summary = render compact text from HeroSnapshot fields
       │     components_summary = render top-12 cards (capped) per component_type
       │     complete_json("follow_up", v=1, response_model=FollowUpAnswer)
       │
       └─ response → thread.push({question, state: ok, answer})
             │       state.answer.tab_hint validated against 5 tab IDs
             └─ "See Valuation tab →" → onJumpToTab(validTab) → setActiveTab + close overlay
```

### 竞态修复

新加 AbortController 在 `SavedThesisProvider` 与 `WatchlistProvider` 的 refresh 中：

1. logout 中 prev fetch 在飞 → `controller.abort()` 撤销，rejection 进 catch 吞掉
2. fetch 已 resolve 但 setItems 未跑 → `if (!controller.signal.aborted) setItems(...)` 守住一帧内 race
3. 组件 unmount → cleanup useEffect 触发最终 abort

### 设计决策

- **`require_pro` 而非 `get_optional_user`**：follow-up 烧 LLM 预算，与 Pro 节点同等门控
- **BUCKET_RECALCULATE 共享配额**：30/day per IP；与 DCF recalc 共池避免 Pro 用户用一个端点喂另一个
- **`tab_hint` 由 LLM 返回但客户端严格验证**：LLM 返回 "moat" 或 invalid 字符串时 `validTab=null`，跳转按钮不显示
- **Watchlist 点击 = 重分析 而非 通知 panel**：用户点 sidebar ticker 是想看最新分析，不是查看历史阈值。点击合成 fake HistoryEntry 走 handleSubmitTicker 路径
- **FollowUpSection `key={ticker}` 强制 remount**：换 ticker 时 thread / input state 干净重置，避免"AAPL 问的问题挂在 MSFT 视图上"
- **`hasPending` 检查阻止双 Enter**：连按 Enter 时 `idx = thread.length` 闭包共享 stale 值会让两个更新都打到同一 thread 槽位

### 已知未做

- Watchlist cron + Resend 告警 — schema 已就绪（`last_checked_at` 等），需要单独 follow-up
- Free 用户提示 "Upgrade to Pro" 但无升级流程链接
- ThresholdDialog 无 ESC 键 / focus trap
- Save / Watch 失败仅 console.warn 无 toast

### 验证

- TS / lint 通过；冒烟测试：401（无 auth）、403（free 用户 Pro endpoint）、404（不存在 share id）、200（frontend root）
- prompts loader：`load_prompt('follow_up', version=1)` OK（temp=0.4, max=1200）

---

## v0.9.0 — Save Thesis + Share Link（Phase 2）

**日期：** 2026-05-01

### 概要

让 Pro 用户把当前 canvas 的分析"钉住"成一份 snapshot，几周后回访可以看到关键字段如何漂移；同时提供公开 `/s/<uuid>` URL 给非用户分享。这是 Verdict-First 重构后第一个粘性钩子 — 一次性工具变成"我能记住当时怎么想"的工具。

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/services/saved_thesis.py` | `SavedThesis` ORM：UUID v4 字符串主键（避免遍历），`user_id` FK 含 ON DELETE CASCADE，`hero_snapshot` 与 `components_snapshot` 用 Postgres JSONB（hero 是摘要供 sidebar 廉价 diff，components 是 full ComponentInstruction[] 供 share 视图复原）。CRUD helpers `create_thesis` / `list_for_user` / `get_owned` / `get_public` / `delete_owned` |
| `backend/backend/services/watchlist.py` | `WatchlistItem` ORM placeholder — schema 此处定义，code path 在 v0.10 启用。包含在 v0.9 是因为同一份 alembic 迁移建两张表 |
| `backend/backend/api/saved_thesis.py` | 5 个端点：POST `/api/saved-thesis`（创建）/ GET（列表 mine）/ GET `/{id}`（读 mine）/ DELETE `/{id}`（删 mine）/ GET `/api/share/thesis/{id}`（公开只读，仅 `is_public=true` 才返回） |
| `backend/alembic/versions/20260501_0002_saved_thesis_and_watchlist.py` | Alembic 迁移：建 `saved_theses` 和 `watchlist_items` 两张表（后者由 v0.10 使用） |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/alembic/env.py` | 加 `SavedThesis` + `WatchlistItem` 模型导入（autogenerate 注册） |
| `backend/backend/main.py` | 加 `saved_thesis_router` 注册 |

### 数据库 schema

```sql
saved_theses (
  id              VARCHAR(36) PRIMARY KEY,         -- UUID v4
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ticker          VARCHAR(8) NOT NULL,
  title           VARCHAR(200),
  is_public       BOOLEAN NOT NULL DEFAULT TRUE,
  hero_snapshot   JSONB NOT NULL,                  -- HeroSnapshot 字段
  components_snapshot JSONB NOT NULL,              -- ComponentInstruction[]
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
INDEX (user_id), INDEX (ticker)
```

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/lib/api-client.ts` | 通用 `apiRequest<T>(path, opts)` 包裹 fetch，标准化 FastAPI `{detail: ...}` 错误为 `ApiError` 抛出。`credentials: "include"` 透传 cookie auth |
| `frontend/src/lib/saved-thesis-api.ts` | createSavedThesis / listSavedTheses / getSavedThesis / deleteSavedThesis / getPublicThesis |
| `frontend/src/context/saved-thesis-context.tsx` | `SavedThesisProvider` 包 Auth 之下；`refresh` 在 status 变化时拉取，logout 时立即清；`save` 调 API 后乐观 prepend；`remove` 乐观 filter |
| `frontend/src/components/canvas/hero-actions.tsx` | Hero 右侧的 [Save] / [Share] 按钮组。已 saved 时按钮变 [Saved][Share]，[Share] 复制 `/s/<uuid>` 到剪贴板（fallback 到 `window.prompt`）。匿名/Free 用户按钮 disabled 显示 "Sign in" tooltip |
| `frontend/src/app/s/[id]/page.tsx` | 公开只读分享路由：调 `/api/share/thesis/{id}`，复用 `<VerdictHero isSnapshotView>` + `<CanvasTabs>`，顶部 banner 标识 "shared thesis · snapshot · {date}"，提供 "Run your own analysis" 引流 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/lib/types.ts` | 新增 `HeroSnapshot` / `SavedThesisSummary` / `SavedThesisFull` 类型 |
| `frontend/src/components/canvas/verdict-hero.tsx` | `deriveHero` 改为 `export`（share 路由也要派生），返回类型改用共享 `HeroSnapshot`。增加 `isSnapshotView` prop（true 时隐藏 actions + diff strip）；新增 `<HeroActions>` 整合 + 新内联 `SavedDiffStrip` 在重访已 saved 同一 ticker 时显示 MoS / Confidence / Price / Signal 4 项 delta（trend 颜色 + 涨跌图标）；`useState(() => Date.now())` lazy-init 以保持 render purity |
| `frontend/src/components/layout/sidebar.tsx` | 在 History 上方插入 `<SavedThesesSection>`：列出用户所有 saved theses，行点击新窗口打开 `/s/<id>`（仅 `is_public=true`），右侧 hover 显示 X 删除按钮 |
| `frontend/src/app/layout.tsx` | 把 `<HistoryProvider>` 包进 `<SavedThesisProvider>` 包进 `<AuthProvider>`，确保 saved thesis hooks 永远能拿到 auth context |

### 设计决策

- **UUID 主键 vs 整数自增**：share URLs 必须非可遍历（否则随机猜 id 就能 enumerate 别人的 thesis）。UUID v4 满足此要求，加 1 next-step 步骤可以加 confusion。
- **`is_public` 默认 true**：保存的本意通常是分享或对比，private 是少数。用户如果隐私敏感可以未来加切换 UI。
- **JSONB 存 components_snapshot 而非外键到 ComponentInstruction 表**：分析每次都重跑产生新 component 行，没必要规范化。JSONB 可以索引但目前不需要。
- **`/api/share/thesis/{id}` 与 `/api/saved-thesis/{id}` 分开**：前者无授权但只返回 `is_public=true`；后者授权但返回 owner 的所有 saves（无论 is_public）。前端 `/s/[id]` 只走前者。
- **乐观 UI**：save / remove 不等下一次 list 刷新，直接更新 context items。失败时回滚由 API 客户端的 ApiError throw 处理（hero-actions 内部 catch + console.warn）。
- **`isSnapshotView` 的必要性**：未登录访客或访问别人的 share 时，diff strip 拿"我自己的 saved AAPL"对比"share 的 AAPL"，跨用户跨时间比较毫无意义，所以 share 路由传 `isSnapshotView` 抑制 diff strip 和 actions 渲染。

### 拒绝的备选方案

- ❌ **OG 图片 for share link**：next/og 渲染 hero strip 是病毒系数放大器，但 v0.9 不阻塞核心功能，留给后续。
- ❌ **Owner-only viewer page** `/saved/[id]`：当 `is_public=false` 时 sidebar 链接走 `#` 不导航。当前所有 save 默认 public，gap 不显现；后续加私有切换 UI 时再补 owner-only viewer。
- ❌ **Save 按钮在流式期间禁用**：用户可能想 save 部分分析做对比。current 行为允许保存任意 stage。`SavedDiffStrip` 在双方都有数据的字段才渲染 delta，缺字段静默跳过。

### 验证

- TS / lint 通过（与 v0.8 同标准）
- 后端：`/api/saved-thesis`（无 auth）→ 401 ✓；`/api/share/thesis/<bad-uuid>` → 404 ✓
- 已知限制（不阻塞 ship）：401 token 过期不强制 logout、 同 ticker 多次 save schema 允许但 UI 显示单份、Save 失败仅 console.warn

---

## v0.8.0 — Verdict-First UI 重构（Phase 1）

**日期：** 2026-05-01

### 概要

原右侧 canvas 把 19 张分析卡片纵向堆叠在一列里（约 4000–6000px），用户输入 ticker 后要滚 5000px 才能拼出"该不该买、多有把握、为什么"的答案。本次重构按"答案→佐证→深挖→透明度"分层信息架构：

1. **Verdict Hero**（sticky 顶部，5 字段）：signal pill / margin of safety / confidence / 高严重风险计数 / 一句话 thesis + entry/exit 价格区间。从已经在流的组件中派生，不重算。
2. **5 个 Tab** 把 19 张卡片按角色分组：Verdict（推荐+论点）/ Valuation（估值数字）/ Strategy（时机/情绪）/ Risks & Moat（风险+护城河）/ Sources（来源 + 推理 trace）。
3. **Conversation panel 折叠 rail**：流式中保持 420px 满展开（看进度+推理）；`status==='complete'` 后自动折叠成 56px rail。点 rail 弹出 420px overlay（不挤压 canvas，点遮罩或 X 关闭）。
4. **流式 UX**：tab 不自动切换（避免抢焦点），非活动 tab 收到新卡片时脉冲红点提示。`risk_factors_card.severity == 'high'` 数 > 0 时 Hero 的 Risks 块变红可点跳 Risks tab。

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/canvas/tab-groups.ts` | `TabId` 类型 + `TAB_ORDER` / `TAB_LABELS` / `tabFor(componentType)` 映射。19 张卡 → 5 tab，未识别类型 fallback 到 Sources |
| `frontend/src/components/canvas/verdict-hero.tsx` | Hero 组件 + `deriveHero(components)`：从 `investment_thesis_card` / `strategy_dashboard` / `risk_factors_card` / `valuation_gauge` 派生 12 字段。recommendation 优先于 strategy.signal。Free tier 无 thesis card 时用 strategy.signal 兜底 |
| `frontend/src/components/canvas/canvas-tabs.tsx` | shadcn Tabs 包裹的 5-tab 壳。`seenCounts` lazy-init 全 tab，pulse-dot 仅对**之后**到达的卡片触发。Sources tab 末尾追加 `<ReasoningTrace>` |
| `frontend/src/components/canvas/reasoning-trace.tsx` | 推理 trace 卡。从原 `ConversationPanel` 的 per-node accordion 搬过来，按节点分组渲染 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/analysis-canvas.tsx` | 扁平 `.map` 替换为 `<VerdictHero>` + `<CanvasTabs>` 双区。Hero 取自然高度，Tabs 内部独立滚动。`key={activeEntryId}` 强制切换缓存条目时 `seenCounts`/`activeTab` 重置 |
| `frontend/src/components/conversation-panel.tsx` | 加 `collapsed` prop + `ConversationRail`（56px 单按钮）变体；`showCloseButton`+`onClose` 用于 overlay 模式；首次完成时一次性 localStorage tooltip。**移除** per-node 推理 accordion（搬到 Sources tab） |
| `frontend/src/components/layout/app-shell.tsx` | 新增 `overlayOpen` 状态。`showRail = !isStreaming && ticker !== null`、`showOverlay = showRail && overlayOpen` 由 `displayStatus` 推导（不用 setState-in-effect）。Overlay 用 `absolute inset-0` 黑色 backdrop + `absolute left-[56px]` 浮层，点击 backdrop 或 X 按钮关闭 |

### 设计决策

- **Tabs 不自动切换**：避免抢焦点；脉冲红点提示新卡到达，由用户主动点击。
- **Hero 单一来源**：直接读组件 props，不重算 → 永远不会和 tab 内部卡片不一致。
- **推理 trace 移至 Sources tab**：折叠后 chat 只剩进度+verdict+输入框，避免折叠/展开间用户重读推理。
- **Conversation panel 折叠为 rail 而非全隐藏**：保留 follow-up 提问的入口（Phase 3 会接 LLM）。
- **流式期 vs 完成期分离 layout**：流式时 chat 重要，完成时 canvas 重要。Layout 跟随用户当前意图。

### 拒绝的备选方案

- ❌ **左侧 TOC 导航条**：scroll-spy 只是给那条 5000px 滚动加目录。把"信息过载"当导航问题处理 — 但实际是注意力问题。Tabs **隐藏**非当前组才是关键。
- ❌ **chat 移到 hero 下变水平条**：保留 chat 可见性诱人，但牺牲垂直空间（图表的稀缺轴）。折叠到 rail 更诚实。
- ❌ **游戏化徽章 / 社交 feed / 未触发的 AI 弹窗**：受众是投资人不是社交产品用户。

### 验证

- TS 通过（仅 fcf-chart/revenue-chart 已知 recharts 类型问题）
- ESLint 通过（react-hooks/refs、react-hooks/set-state-in-effect、react-hooks/static-components 全部 0 错）
- 手动验证：ticker 输入 → hero 字段渐入 → tab 计数 badge 增长 → 完成后 chat 折叠 → 点 rail 展开 overlay → 点遮罩关闭

---

## v0.7.2 — Admin 运行时切换 LLM provider

**日期：** 2026-04-28

### 概要

把 LLM 的 provider / model / api_key 从「启动期 env 固定」升级为「admin 运行时可改」。
admin `PATCH /api/admin/settings` 改完之后下次请求自动用新配置；不需重启进程；
不影响 in-flight 请求；不重置 token 计费历史。

### 用法

```bash
# 切到 OpenAI
curl -X PATCH \
  -H "Authorization: Bearer $AQ_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "llm_api_key": "sk-openai-xxx",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4o-mini"
  }' \
  http://localhost:8000/api/admin/settings

# 一键回 .env 默认
curl -X POST -H "Authorization: Bearer $AQ_ADMIN_TOKEN" \
  http://localhost:8000/api/admin/settings/reset

# 单独切 thesis（task_tag）走高端模型，其它仍走 DeepSeek
curl -X PATCH ... -d '{
  "llm_narrative_api_key": "sk-openai-xxx",
  "llm_narrative_base_url": "https://api.openai.com/v1",
  "llm_narrative_model": "gpt-4o"
}'
```

### 变更文件

| 文件 | 变更 |
|------|------|
| `backend/services/runtime_settings.py` | `EffectiveSettings` 加 6 个 LLM 字段；`as_dict(redact=True)` 把 api_key 改成 `***last4`；新增 `redact_overrides`、`has_llm_overrides`、`LLM_PROVIDER_FIELDS` / `REDACTED_FIELDS` 常量；`_coerce` 验证 https URL |
| `backend/services/llm/client.py` | 新增 `_effective_llm_config()`（override 优先，env fallback）+ `invalidate_llm_client()`；`_build_client` / `is_llm_configured` 改读 runtime |
| `backend/services/llm/__init__.py` | 公开 `invalidate_llm_client` |
| `backend/api/admin.py` | `SettingsPatch` 加 6 个字段；`patch_settings` 在 LLM 字段动了时调 `invalidate_llm_client`，applied echo 自动 redact 秘钥；`reset_settings` 同样在有 LLM override 时 invalidate；GET 响应过 `redact_overrides` |

### 安全设计

- secret 字段（`llm_api_key` / `llm_narrative_api_key`）在所有 admin 响应里都 redacted（`***last4` 或 `***`），秘钥**只能写不能读**
- bad URL（非 https / 非 localhost）在 PATCH 阶段被 400 拒绝，避免后续 LLM 调用才发现
- empty string PATCH = "remove override, fall back to env"（不是"清空配置"）
- 紧急停 LLM 的正确方式：`PATCH llm_daily_budget_usd=0`（BudgetGate 立即拦截，所有节点降级），不是改 api_key

### 已知限制

- 多 worker 部署（`uvicorn --workers N`）下，admin PATCH 只影响接收该 PATCH 的 worker；其余 worker 仍用旧配置直到下次重启或自身收到 PATCH。本期为单实例 MVP 设计。Multi-worker 解决方案在 follow-up（Redis pub-sub 通知所有 worker invalidate）。
- 没有"切换历史"审计日志。如果需要追溯"今天上午谁把 model 改成了 gpt-4o"，目前只能查 admin token 谁拿着。

### 验证

- 10 个单元断言（runtime_settings + client）
- 7 个 HTTP E2E（GET 初态/PATCH/再 GET/bad URL/未知字段/reset/numeric-only）

### 相关

- 实现自 [ADR 006](docs/decisions/006-unified-llm-client.md) 「Future extension points」中的「Multi-Provider 路由表（admin 在 RuntimeSettings 里热改）」
- 详细推演见 PR description

---

## v0.7.0 — 认证 + 订阅分级（Phase 2）

**日期：** 2026-04-25

### 概要

引入完整的用户身份系统。三种登录方式（邮箱/密码、Magic Link、Google OAuth）共用同一份用户/身份表，PostgreSQL 持久化，JWT cookie 维持会话。同时把 5 个 LLM Pro 节点中的 4 个（thesis / qualitative / risk_yoy_diff / moat）按 `user.tier` 门控：免费用户看到锁定预览卡片 + Upgrade CTA，付费用户跑完整 LLM 流程。Admin 通过 `PATCH /api/admin/users/{email}/tier` 手动升降级（Stripe 留待后续）。

### 后端变更

#### 新增依赖

`sqlalchemy[asyncio]` / `asyncpg` / `alembic` / `bcrypt` / `python-jose[cryptography]` / `authlib` / `itsdangerous` / `email-validator`

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/services/db.py` | Async SQLAlchemy engine + session factory + `is_db_configured()` 优雅降级 + lifespan 关闭钩子 |
| `backend/backend/services/auth/__init__.py` | Auth 模块对外接口（User / AuthService / 各 dependencies） |
| `backend/backend/services/auth/models.py` | `User` 与 `IdentityProvider` ORM；email 唯一，每用户每种 auth 方式至多一条 identity 行 |
| `backend/backend/services/auth/passwords.py` | bcrypt 哈希 / 校验（cost=12） |
| `backend/backend/services/auth/tokens.py` | JWT (HS256) 签发 / 解码；7 天 TTL；`SessionClaims` dataclass |
| `backend/backend/services/auth/service.py` | `AuthService`：register/login/upsert_magic_link_user/upsert_google_user/set_tier；统一处理 identity 行链接和 last_login_at |
| `backend/backend/services/auth/magic_link.py` | `itsdangerous` 签名 token + Resend HTTP API 发件；无 key 时打印到 stderr + 返回 `dev_link` 兜底 |
| `backend/backend/services/auth/google_oauth.py` | authlib OIDC 客户端配置 |
| `backend/backend/services/auth/dependencies.py` | FastAPI deps：`get_current_user` / `get_optional_user` / `require_pro` / `require_admin_tier`；从 `Authorization: Bearer` 或 `aq_session` cookie 读 token |
| `backend/backend/api/auth.py` | 8 个路由：邮箱注册/登录、Magic Link 发送/验证、Google start/callback、me、logout |
| `backend/backend/agents/nodes/_pro_gate.py` | 共享 helper：`is_pro_user(state)` 与 `emit_lock(...)`；4 Pro 节点共用 |
| `backend/alembic/env.py` + `script.py.mako` + `versions/20260425_0001_init_users.py` | Alembic 异步迁移基础设施 + 首次迁移（users / identity_providers + CHECK 约束） |
| `backend/alembic.ini` | Alembic 配置（DSN 由 env 注入） |
| `backend/.env.example` | 完整的 env 变量模板 + 说明 |
| `frontend/src/lib/auth-api.ts` | 类型化 fetch wrappers：register/login/sendMagicLink/verifyMagicLink/fetchMe/logout |
| `frontend/src/context/auth-context.tsx` | `<AuthProvider>` + `useAuth()` hook；`status` ∈ {loading, authenticated, anonymous} |
| `frontend/src/app/auth/login/page.tsx` | 三 tab 登录页（Password / Magic link / Google） |
| `frontend/src/app/auth/register/page.tsx` | 邮箱密码注册 |
| `frontend/src/app/auth/magic-link/verify/page.tsx` | 接 `?token=...`，调 verify 端点 |
| `frontend/src/components/analysis/pro-locked-card.tsx` | 共享锁定预览卡（4 个 Pro 节点的 locked component_type 都映射到这个） |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/config.py` | 新增 `database_url` / `default_user_tier` / `jwt_*` / `magic_link_*` / `resend_*` / `google_oauth_*` 字段 |
| `backend/backend/main.py` | 加载 `auth_router`；新增 `SessionMiddleware`（OAuth state cookie）；lifespan 关闭 DB engine |
| `backend/backend/api/routes.py` | `/analyze` 注入 `Depends(get_optional_user)`；从 user 读 tier 写入 `initial_state["user_tier"]` |
| `backend/backend/api/admin.py` | 新增 `PATCH /api/admin/users/{email}/tier` 手动升降级 |
| `backend/backend/models/agent_state.py` | 新增 `user_tier: str` 字段 |
| `backend/backend/agents/nodes/{investment_thesis,qualitative_analysis,risk_yoy_diff,moat_analysis}.py` | 节点开头加 `if not is_pro_user(state): return emit_lock(...).payload` 短路 |
| `frontend/src/app/layout.tsx` | 在 `HistoryProvider` 外层包 `AuthProvider` |
| `frontend/src/lib/types.ts` | 新增 `Tier` / `AuthUser` / `AuthSessionResponse` 类型 |
| `frontend/src/components/component-registry.ts` | 注册 4 个 `*_locked_card` 全部映射到 `pro-locked-card.tsx` |

### 数据库 schema

```sql
users (
  id, email UNIQUE, password_hash NULL, tier CHECK (free|pro|admin),
  is_active, email_verified, display_name,
  created_at, updated_at, last_login_at
)
identity_providers (
  id, user_id FK→users, kind CHECK (email_password|magic_link|google),
  external_id, created_at, last_used_at,
  UNIQUE (user_id, kind), UNIQUE (kind, external_id)
)
```

### 验证覆盖

- ✅ bcrypt 哈希 + 校验 + JWT 签发/解码往返
- ✅ Magic-link `itsdangerous` 签名 token 往返；无 RESEND_KEY 时返回 `dev_link`
- ✅ 4 个 Pro 节点 free 路径全部正确发出 `*_locked_card` ComponentEvent，state 字段为 None
- ✅ 12 个 LangGraph 节点全部装载，15 个 API 路由全部注册
- ✅ Frontend 类型干净

### 已知限制 / 后续

- Stripe 订阅暂未接入 — Pro 升级走 admin 手动 PATCH
- 邮箱验证流程暂未实现（Magic-link 自动标记 `email_verified=True`，密码注册标记为 False）
- 没有"忘记密码"流程（用户可以走 Magic-link 重新登录）

---

## v0.6.0 — 5 个 LLM Pro 节点（Phase 3）

**日期：** 2026-04-25

### 概要

在 LLM 基础设施（v0.5.0）之上叠加 5 个研究密集型 LLM 节点，把分析管线从 8 节点扩展到 12 节点。每个 Pro 节点统一遵循「**LLM 输出 → Pydantic 校验 → 逐字引文核验 → 渲染**」防幻觉链路。

### 管线变更

```
v0.5.0: SEC → 财务健康 → DCF → 相对估值 → 情绪 → 事件影响 → 策略 → 溯源（8 节点）
v0.6.0: ... → 策略 → 定性分析(MD&A+RF) → YoY风险对比 → 护城河评分 → 投资论点 → 溯源（12 节点）
```

### 5 个新节点

| # | 节点 | 输入数据 | LLM 调用 | 输出 |
|---|------|---------|---------|------|
| 1 | `investment_thesis` | 全部上游 state | 1 次 (`thesis` task_tag) | 结构化研报：headline + bull/bear/risks + recommendation + confidence |
| 2 | `qualitative_analysis` (MD&A) | 10-K Item 7 | 1 次 (`mdna`) | tone + forward guidance + 增长驱动 + 管理层担忧 + 逐字引文 |
| 3 | `qualitative_analysis` (Risk Factors) | 10-K Item 1A | 1 次 (`risk_factors`) | 8 类风险分类 + Top 5 risks 带 severity + concentration risk |
| 4 | `risk_yoy_diff` | 当年 + 去年 10-K | 1 次 (`risk_yoy_diff`) | new / removed / escalated / de-escalated 四桶变化 + 双源引文核验 |
| 5 | `moat_analysis` | 10-K Item 1 | 1 次 (`moat`) | Helmer 7 Powers 各 0-10 评分 + classification + 不可核验时 demote 到 0 |

#### MD&A + Risk Factors 在同一节点并行（asyncio.gather）

`qualitative_analysis` 一次拉取 10-K，并行抽取 MD&A 和 Risk Factors 两节，部分失败仍然展示成功的那部分卡片。

### 防幻觉机制（贯穿 5 个节点）

1. **System prompt 强约束**：明令"只能从 USER_CONTENT 边界内提取，禁止使用训练数据知识"。
2. **Pydantic 模型校验**：每个 prompt 对应一个 response_model，类型/枚举/长度全验。
3. **逐字引文核验**：所有 `notable_quotes` / `top_risks[*].quote` / `evidence_quote` 都经过 `verify_quotes()` —— 必须是源文本的 substring（白空格归一化 + smart-quote 归一化），否则丢弃整条 risk / 把 power 评分 demote 到 0。

### 关键实现细节

#### 后端新增

| 类别 | 文件 |
|------|------|
| 共用工具 | `services/tenk_parser.py`（`extract_mdna` / `extract_risk_factors` / `extract_business` 三层正则回退 + `smart_truncate` 头尾截断 + `truncate_head` 优先级头部截断） |
| Prompts | `prompts/{investment_thesis,mdna_analysis,risk_factors,risk_yoy_diff,moat_analysis}_v1.yaml` |
| 节点 | `agents/nodes/{investment_thesis,qualitative_analysis,risk_yoy_diff,moat_analysis}.py` |
| SEC | `services/sec_client.py` 新增 `fetch_10k(cik, n_back)` 含 6 条 FIFO HTML 缓存；同时**修复 8-K 抓取的嵌套 JSON 路径 bug**（之前一直静默返回空） |

#### 前端新增

| 文件 | 说明 |
|------|------|
| `analysis/investment-thesis-card.tsx` | Bull/Bear/Risks 三栏 + recommendation 徽章 + confidence |
| `analysis/qualitative-insights-card.tsx` | tone 徽章 + forward guidance + 双栏（drivers/concerns）+ verbatim quotes |
| `analysis/risk-factors-card.tsx` | 风险分类徽章条 + Top risks 列表（category 图标 + severity 徽章 + 引文）+ concentration callout |
| `analysis/risk-yoy-diff-card.tsx` | 4 桶 2x2 网格；escalated/de_escalated 显示 prior↔current 并排引文 |
| `analysis/moat-analysis-card.tsx` | 7 power 渐变进度条 + primary badge + verbatim 引文 + overall = max(scores) |

### 成本影响

| 节点 | DeepSeek 单次 | GPT-4o 单次 |
|------|---------------|-------------|
| sentiment | ~$0.0005 | ~$0.01 |
| event_filter + event_analysis | ~$0.0007 × 2 | ~$0.015 × 2 |
| mdna | ~$0.001 | ~$0.025 |
| risk_factors | ~$0.001 | ~$0.025 |
| risk_yoy_diff | **~$0.0035**（最贵） | **~$0.10**（最贵） |
| moat | ~$0.001 | ~$0.025 |
| thesis | ~$0.0008 | ~$0.02 |
| **完整分析** | **~$0.01** | **~$0.25** |

每天 $5 全局预算可跑 **~50 次完整分析**（DeepSeek）或 **~20 次**（GPT-4o）。

---

## v0.5.0 — LLM 基础设施 + 成本围栏（Phase 1）

**日期：** 2026-04-24

### 概要

把分散在 `llm_sentiment.py` / `event_impact.py` 中的两处 LLM 调用收编到统一的 `LLMClient` 里，建立 Prompt YAML 库 + Provider 抽象 + Token 计费，并叠加三层成本围栏（IP 限流 + per-IP LLM 预算 + 全局 LLM 预算）。新增 admin API 让运维不重启就能调阈值。

### 后端新增

| 文件 | 说明 |
|------|------|
| `services/llm/__init__.py` | 模块对外接口 |
| `services/llm/client.py` | `LLMClient.complete_json(prompt_name, variables, response_model, task_tag)` 统一入口；含模板渲染 / 输入净化 / 重试 / Pydantic 校验 / 计费 |
| `services/llm/providers.py` | `OpenAICompatibleProvider`（DeepSeek / OpenAI / 任何 OpenAI 协议兼容） |
| `services/llm/sanitize.py` | 输入净化 + 注入检测 + `<<<USER_CONTENT>>>` 边界包裹 |
| `services/llm/accounting.py` | `AccountingStore`：每次调用结构化日志 + 24h 滑动窗成本聚合 + per-IP 维度 |
| `services/llm/budget.py` | `BudgetGate`：每次 LLM 调用前过双闸（global + per-IP），命中抛 `LLMBudgetExceeded` |
| `services/llm/errors.py` | `LLMError` 基类 + `LLMConfigError` / `LLMProviderError` / `LLMParseError` / `LLMBudgetExceeded` |
| `services/runtime_settings.py` | env 默认 + 内存层 admin 覆盖；`RuntimeSettings.snapshot()` / `update()` / `reset()` 线程安全 |
| `services/request_context.py` | `contextvars.ContextVar` 透明传递 client_ip 到所有 async 调用栈 |
| `services/rate_limit.py` | `IPRateLimiter` 24h 滑动窗 per-bucket per-IP 计数 |
| `prompts/__init__.py` | YAML 模板加载器 + 缓存 + 启动期校验 |
| `prompts/{sentiment,event_filter,event_analysis}_v1.yaml` | 从 v0.3 / v0.4 节点中迁出的 prompt |
| `api/admin.py` | `/api/admin/{settings, settings/reset, usage}` Bearer-token 鉴权 |

### 后端修改

- `services/llm_sentiment.py` / `agents/nodes/event_impact.py` 全部改走 `LLMClient.complete_json`，原 prompt 字符串迁出到 YAML
- `api/routes.py` 在 `/analyze`、`/recalculate-dcf` 入口先过 `_enforce_rate_limit`，并 `bind_client_ip(ip)` 进 contextvar
- `main.py` 注册 admin_router；shutdown 钩子改走 `services.llm.close_llm_client`
- `config.py` 新增 `llm_*` / `rate_limit_*` / `admin_token` 字段
- `pyproject.toml` 新增 `pyyaml`

### Admin API 用法

```bash
# 看 24h 花费 + 限流命中
curl -H "Authorization: Bearer $TOKEN" /api/admin/usage

# 紧急提预算
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -d '{"llm_daily_budget_usd": 20.0}' \
  /api/admin/settings

# 一键回到 .env 默认
curl -X POST -H "Authorization: Bearer $TOKEN" /api/admin/settings/reset
```

### 验证覆盖

- ✅ 限流：第 4 次请求被拒（429 + Retry-After 86394）
- ✅ 全局预算：模拟支出 $7 时所有 LLM 调用抛 `LLMBudgetExceeded(scope=global)`
- ✅ Admin 动态调整：PATCH 后下次请求立即生效
- ✅ 不重启回归默认：`/settings/reset` 清空覆盖

---

## v0.4.0 — 事件影响分析（Event Impact Analysis）

**日期：** 2026-04-22

### 概要

在消息面情绪分析基础上，新增事件影响分析节点。通过两步 LLM 调用，从权威新闻和 SEC 8-K 文件中筛选出真正影响估值的重大事件，自动调整 DCF 参数并重算内在价值。同时大幅改进了新闻获取和过滤机制：公司名匹配、7 天分批获取确保 30 天覆盖、权威来源白名单、SEC 8-K 文件整合。分析管线从 7 个节点扩展至 8 个节点。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 事件影响 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/event_impact.py` | 事件影响分析节点（约 490 行）。两步 LLM 调用：(1) 筛选有估值影响的新闻 (2) 分析参数调整。应用调整后调用 `compute_dcf()` 自动重算。发射 `event_impact_card` 组件。 |
| `backend/backend/agents/nodes/event_impact_math.py` | 纯计算函数（无 I/O）：`PARAMETER_REGISTRY` 参数注册表、`apply_parameter_adjustment()` 单参数调整、`apply_all_adjustments()` 全参数映射（含扩展参数：risk_adjustment→WACC、revenue_adjustment→增长、margin_adjustment→增长*0.5、fcf_one_time_adjust→FCF）、`recalculate_dcf()` 调用已有 DCF 模型、`validate_filter_response()` 和 `validate_analysis_response()` 校验 LLM 返回值。 |
| `backend/tests/agents/nodes/test_event_impact_math.py` | 事件影响数学函数的单元测试，覆盖参数调整、映射逻辑、DCF 重算和校验函数。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `event_impact_result: dict[str, Any] | None` 字段。 |
| `backend/backend/agents/value_analyst.py` | 导入 `event_impact_node`，新增节点，修改边：`event_sentiment` → `event_impact` → `strategy`。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `event_impact_result: None`。 |
| `backend/backend/agents/nodes/strategy.py` | 优先使用 `event_impact_result.recalculated_dcf.intrinsic_value_per_share`（如存在），否则回退到原始 `dcf_result`。新增 `event_impact_result` 参数传入 `_run_strategy`。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中追加事件影响摘要，如有重算 DCF 使用新的内在价值。 |
| `backend/backend/main.py` | 导入 `close_event_impact_client`，在 lifespan shutdown 中调用。 |
| `backend/backend/services/finnhub_client.py` | `get_company_news()` 从单次请求改为 7 天分批并发获取（semaphore=3），按 `id` 去重，按 `datetime` DESC 排序，确保 30 天完整覆盖。 |
| `backend/backend/agents/nodes/event_sentiment_math.py` | 新增 `TICKER_ALIASES`（40+ ticker→公司名映射）、`_headline_mentions_ticker()` 词边界匹配含公司名、`_text_mentions_ticker()` 摘要检查、改进 `_compute_relevance_score()` 新评分体系（4/3/2/0）、`filter_by_authoritative_source()` 白名单过滤（Reuters/Bloomberg/WSJ/FT 等 20+ 权威来源）、`_extract_article_timestamp()` 日期提取排序。删除未使用的 `_headline_mentions_other_ticker()` 和不可达的死代码分支。 |
| `backend/backend/agents/nodes/event_sentiment.py` | 新增 SEC 8-K 文件获取（通过 `sec_client.get_recent_8k_filings()`），转为 article 格式并入文章列表。新增 `_log_date_distribution()` 调试日志。LLM 分析上限从 15 篇提升到 20 篇。 |
| `backend/backend/services/llm_sentiment.py` | LLM 文章上限从 15 提升到 20，`max_tokens` 从 2000 提升到 2500。`_validate_llm_response()` 改为创建副本避免修改原 dict。SYSTEM_PROMPT 要求 `key_events` 按重要性排序。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/event-impact-card.tsx` | 事件影响可视化卡片（约 320 行）。包含：摘要 + 置信度指示器、参数对比表（Original → Adjusted + delta 箭头 + reasoning tooltip）、重算内在价值显示、触发事件列表（可点击链接 + 来源 + 日期）。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `event_impact_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "event_impact", label: "Analyzing Event Impact" }`（位于 `event_sentiment` 和 `strategy` 之间）。 |

### 两步 LLM 分析流程

```
Step 1 — 筛选: 输入所有文章 → LLM 排除常规分析师评级/泛市场评论/已定价业绩
                       → 返回 impactful_indices + reasoning
Step 2 — 分析: 输入筛选文章 + 当前 DCF 假设 → LLM 返回参数调整建议
                       → 每个参数: {type: "delta"/"multiplier"/"absolute", value, reasoning} | null
```

### 参数调整映射

| 直接参数 | 调整方式 | 作用于 |
|----------|----------|--------|
| growth_rate | delta (%) | FCF 增长率 |
| terminal_growth_rate | delta (%) | 永续增长率 |
| discount_rate | delta (%) | WACC/折现率 |

| 扩展参数 | 映射方式 | 实际影响 |
|----------|----------|----------|
| risk_adjustment | 累加到 discount_rate | 风险溢价变化 |
| revenue_adjustment | 乘到 growth_rate | 收入轨迹调整 (0.95 = 减 5%) |
| margin_adjustment | 0.5x 权重加到 growth_rate | 利润率变化部分传导到 FCF |
| fcf_one_time_adjust | 直接替换 latest_fcf | 一次性 FCF 调整 |

### 新闻过滤改进

| 改进项 | 说明 |
|--------|------|
| 公司名匹配 | 40+ ticker→公司名映射 (NVDA→"nvidia", AAPL→"apple")，词边界正则 |
| 相关度评分 | 4=标题含ticker/公司名, 3=summary+related, 2=唯一related, 0=排除 |
| 权威来源白名单 | Reuters/Bloomberg/WSJ/FT/CNBC 等 20+ 家 (SEC 8-K 始终保留) |
| 7天分批获取 | 解决 Finnhub 单次请求结果上限问题，确保 30 天覆盖 |
| SEC 8-K 整合 | 获取最近 30 天 8-K 文件，转为 article 格式，高优先级处理 |
| 双排序 | 相关度 DESC + 日期 DESC，max_articles=30 |

### 代码质量修复（审核后）

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `close_event_impact_client()` 未在 main.py shutdown 中调用 | HIGH | 添加到 lifespan shutdown |
| `_compute_relevance_score` 中 `ticker_in_related` 检查位于 `not ticker_in_related` 分支内（不可达代码） | HIGH | 移除不可达分支 |
| 未使用的 `_headline_mentions_other_ticker()` 函数 | HIGH | 删除死代码 |
| `_validate_llm_response()` 就地修改传入的 dict | HIGH | 创建 shallow copy 避免修改原 dict |
| `event_impact.py` 中 LLM 返回的索引未过滤负数 | MEDIUM | `if 0 <= i < len(articles)` 替代 `if i < len(articles)` |

### 文档体系重构

> v0.4.0 同步完成了文档体系的拆分和全面重写。

#### ARCHITECTURE.md 拆分

原单一 ARCHITECTURE.md 拆分为三层文档体系:

| 层级 | 内容 | 文件 |
|------|------|------|
| 系统全景 | 架构图、请求生命周期、API 协议、运行方式 | `ARCHITECTURE.md` |
| 节点详情 | 8 个节点各自的 I/O、算法、假设、降级 | `docs/nodes/01~08` |
| 决策记录 | 5 个 ADR (架构决策记录) | `docs/decisions/001~005` |

#### 节点文档全面重写 (docs/nodes/)

8 个节点文档全部按统一模板重写，新增内容:

| 新增内容 | 说明 |
|----------|------|
| 子字段访问表 | 每个节点从 State 中具体读取哪些子字段，标记必需/可选 |
| Python 类型注解的输出结构体 | 每个输出 dict 的完整字段、类型、范围 (可复制为代码参考) |
| NVDA 输入/输出示例 | 每个节点都有真实的 NVDA 示例 JSON |
| 跨节点引用链接 | 输入引用来源节点文档，输出引用消费节点文档 |

#### 文档准确性验证

通过源码对照验证，发现并修复以下文档错误:

| 节点 | 问题 | 修复 |
|------|------|------|
| Node 2 | health_assessment 核心算法与阈值表矛盾 | 重写算法步骤对齐阈值表 |
| Node 4 | delta 公式缺少 `abs()` | 补充 |
| Node 5 | TICKER_ALIASES 数量、key_events 类型、缺少权威来源过滤步骤 | 逐项修正 |
| Node 6 | 4 个 PARAMETER_REGISTRY 边界值错误、必需/可选标记错误 | 全部对照源码修正 |

#### 新增文档

| 文件 | 说明 |
|------|------|
| `MVP-GAP.md` | 最小可上线版本差距分析: 4 类硬性阻碍 + 5 项商业功能 + 4 项安全加固 + 5 项运维就绪 + 4 阶段实施路线图 |
| `CHANGELOG.md` | 本文件。新增「文档体系导航」章节，描述文档地图、各文档作用、人类和 AI Agent 导航指南 |

#### 估值建模评审 (Damodaran 对照)

参照 Aswath Damodaran 的估值方法论对 DCF 实现进行了对照评审，发现:

| 严重度 | 问题 | 位置 |
|--------|------|------|
| CRITICAL | 企业价值未扣除净债务就除以股数（EV→Equity Value 缺少 `- Net Debt` 步骤） | `dcf_model.py:116-118` |
| CRITICAL | 无 terminal_growth < discount_rate 保护（可导致除零） | `dcf_model.py:93` |
| HIGH | Beta 硬编码 1.2（公共事业和科技公司用同一 beta） | `dcf_model.py:37` |
| HIGH | 无风险利率 4.5% 和 ERP 5.5% 硬编码 | `dcf_model.py:35-36` |
| HIGH | 用历史 FCF CAGR 代替基本面增长 (ROIC × Reinvestment Rate) | `dcf_model.py:168-182` |
| MODERATE | 情绪 delta 叠加在 event_impact 之上可能双重计算 | `strategy.py:218` |

### 测试

所有 133 个后端测试通过，包括：
- 新增 `test_event_impact_math.py` 覆盖事件影响数学函数
- `test_event_sentiment_math.py` 新增 8 个测试覆盖公司名匹配、日期排序、summary 字段
- 新增 `TestFilterByAuthoritativeSource` 覆盖权威来源过滤

---

## v0.3.0 — 消息面情绪修正（Event & Sentiment Integration）

**日期：** 2026-04-21

### 概要

新增消息面情绪分析管线，通过 Finnhub（Free plan）获取近期新闻和内部人交易数据，使用 DeepSeek LLM 对新闻进行情绪打分（因 Finnhub `news-sentiment` 为 Premium 功能），综合计算整体情绪评分并调整策略节点的安全边际信号。分析管线从 5 个节点扩展至 7 个节点。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 相对估值 → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/services/finnhub_client.py` | Finnhub HTTP 客户端（懒初始化 `httpx.AsyncClient`）。三个方法：`get_company_news()` 获取 30 天新闻（Free）；`get_news_sentiment()` Premium 情绪数据（Free plan 优雅降级）；`get_insider_sentiment()` 内部人情绪（Free）。 |
| `backend/backend/services/llm_sentiment.py` | DeepSeek LLM 新闻情绪分析。通过 OpenAI 兼容 API 调用 `/chat/completions`，使用 XML 标签 `<articles>` 防止 prompt injection，返回结构化 JSON。包含 `_validate_llm_response()` 校验函数（限制 overall_score ∈ [-1, 1]、confidence ∈ [0, 1]）。 |
| `backend/backend/agents/nodes/event_sentiment.py` | 消息面情绪核心节点。获取新闻 → 尝试 Premium 数据 → LLM 降级分析 → 获取内部人数据 → 综合评分 → 发射 `sentiment_card` 组件。 |
| `backend/backend/agents/nodes/event_sentiment_math.py` | 纯计算函数（无 I/O）：`compute_overall_sentiment()` 60/40 新闻/内部人加权；`compute_sentiment_adjustment()` 安全边际修正（±8%）；`classify_event_type()` 关键词分类。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/main.py` | 导入 `finnhub_client`，在 `lifespan()` 关闭时添加 `await finnhub_client.close()`。 |
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `event_sentiment_result: dict[str, Any] | None` 字段（位于 `relative_valuation_result` 和 `strategy_result` 之间）。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `event_sentiment_result: None`。 |
| `backend/backend/agents/value_analyst.py` | 导入 `event_sentiment_node`，将 `event_sentiment` 节点接入 `relative_valuation` 和 `strategy` 之间。 |
| `backend/backend/agents/nodes/strategy.py` | 新增情绪修正逻辑：读取 `event_sentiment_result`（作为参数传入），提取 `margin_of_safety_pct_delta`，调整安全边际。`_run_strategy` 新增 `event_sentiment_result` 参数。`strategy_result` 新增 `sentiment_delta` 和 `sentiment_note` 字段。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中新增消息面情绪摘要（如 "Event sentiment: Bullish (score: 0.38)"）。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/sentiment-card.tsx` | React 组件（约 487 行），包含三个区块：(A) 情绪仪表盘——半圆形 SVG 仪表（bearish 红 → neutral 黄 → bullish 绿）；(B) 新闻细分——看多/中性/看空分布条、关键事件列表、文章列表（含情绪点、事件类型徽章）；(C) 内部人情绪——MSPR 进度条（-100 到 +100）和净变动。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `sentiment_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "event_sentiment", label: "Analyzing Event Sentiment" }`（位于 `relative_valuation` 和 `strategy` 之间）。 |

### 情绪评分机制

| 数据源 | 权重 | 评分范围 | 获取方式 |
|--------|------|----------|----------|
| 新闻情绪 | 60% | -1.0 到 +1.0 | Finnhub Premium 或 DeepSeek LLM |
| 内部人情绪 | 40% | -1.0 到 +1.0 | Finnhub Free `/stock/insider-sentiment` |

### 安全边际修正规则

| 情绪评分范围 | 标签 | MoS 修正 |
|-------------|------|---------|
| < -0.5 | Very Bearish | -8%（提高买入门槛） |
| -0.5 to -0.2 | Bearish | -4% |
| -0.2 to +0.2 | Neutral | 0% |
| +0.2 to +0.5 | Bullish | +3%（降低买入门槛） |
| > +0.5 | Very Bullish | +5% |

### 降级策略

| 场景 | 行为 |
|------|------|
| 未设置 `AQ_FINNHUB_API_KEY` | 节点跳过，不影响后续分析 |
| Finnhub Free plan（无 Premium 情绪） | 自动使用 LLM 分析新闻 |
| 未设置 `AQ_LLM_API_KEY` / `AQ_LLM_BASE_URL` | LLM 不可用，使用关键词分类 |
| Finnhub 无新闻数据 | news_score = None，仅使用内部人情绪 |
| Finnhub 无内部人数据 | insider_score = None，仅使用新闻情绪 |
| 两者均无数据 | 整体评分为 0 (Neutral)，无修正 |

### 配置

在 `.env` 文件中新增以下配置（均已在 `config.py` 中定义）：
```
AQ_FINNHUB_API_KEY=<your-key>            # 必需: 启用消息面情绪节点
AQ_LLM_API_KEY=<your-deepseek-key>       # 可选但推荐: LLM 新闻情绪分析
AQ_LLM_BASE_URL=https://api.deepseek.com # 可选: OpenAI 兼容 API 地址
AQ_LLM_MODEL=deepseek-chat               # 可选: 模型名称
```

### 测试

新增 35 个单元测试（`backend/tests/agents/nodes/test_event_sentiment_math.py`），覆盖：
- `compute_sentiment_adjustment` 边界值（极端看空 -8% 到极端看涨 +5%）
- `compute_overall_sentiment` 加权逻辑（仅新闻、仅内部人、两者均有、无数据）
- `classify_event_type` 关键词分类（8 种事件类型 + 18 个参数化测试用例）
- 所有 51 个后端测试通过（35 新增 + 16 原有）

### 代码质量修复（审核后）

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `strategy.py` 中 `_run_strategy` 引用未传入的 `state` 变量 | CRITICAL | 将 `event_sentiment_result` 作为显式参数传入 `_run_strategy` |
| LLM 响应仅检查 `overall_score` 是否存在 | HIGH | 新增 `_validate_llm_response()` 校验所有字段类型和范围 |
| LLM 错误响应体被记录到日志（可能泄露敏感信息） | HIGH | 移除 `e.response.text[:200]` 日志，仅记录状态码 |
| 新闻标题直接拼接进 LLM prompt（prompt injection 风险） | HIGH | 使用 `<articles>` XML 标签包裹用户内容 |
| 未使用的 `entity_name` 变量 | MEDIUM | 删除死代码 |

---

## v0.2.0 — 相对估值（市场乘数法）

**日期：** 2026-04-17

### 概要

新增完整的相对估值分析管线，使用市场乘数（Market Multiples）进行自历史对比和同业对比，与现有 DCF 绝对估值形成互补。分析流程现在会产出第二份独立的估值参考意见。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/relative_valuation.py` | 相对估值核心节点（约280行）。计算当前乘数（P/E、P/B、P/S、EV/Revenue、EV/EBIT、EV/FCF、PEG）、历史百分位分析、以及通过 FMP API 的同业对比。向 SSE 流发送 `relative_valuation_card` 组件。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/services/market_data.py` | 新增3个 FMP API 方法：`get_peers()` 通过 `/api/v4/stock_peers` 获取同业股票代码；`get_peer_key_metrics_ttm()` 通过 `/api/v3/key-metrics-ttm` 获取 TTM 关键指标；`get_batch_peer_metrics()` 使用 `asyncio.gather` 进行并发批量查询。 |
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `relative_valuation_result: dict[str, Any] | None` 字段。 |
| `backend/backend/agents/value_analyst.py` | 在 LangGraph 管线中，将 `relative_valuation` 节点接入 `dynamic_dcf` 和 `strategy` 之间。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `relative_valuation_result: None`。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中新增市场乘数摘要（P/E、P/B、P/S），在数据可用时自动包含。 |
| `backend/backend/agents/nodes/strategy.py` | 新增相对估值交叉校验：若同业 P/E 偏差超过 ±20%，生成推理说明。`_run_strategy` 新增 `relative_valuation_result` 参数。 |
| `backend/backend/config.py` | 新增 `.env` 文件自动发现机制（从 `config.py` 向上逐级搜索至仓库根目录），无需手动设置环境变量即可加载 `AQ_FMP_API_KEY`。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/relative-valuation-card.tsx` | React 组件（约340行），包含三个区块：(A) 当前乘数网格——展示 P/E、P/B、P/S、EV/Revenue、EV/EBIT、EV/FCF、PEG 及百分位指示器；(B) 历史百分位条形图——按颜色区分估值区间；(C) 同业对比表——目标公司、同业行、行业中位数行。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `relative_valuation_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "relative_valuation", label: "Comparing Market Multiples" }`。 |

### 降级策略

| 场景 | 行为 |
|------|------|
| 未设置 `AQ_FMP_API_KEY` | 节点跳过所有依赖价格的乘数计算，返回 `price_available: false`。前端显示提示横幅。 |
| 已设置 FMP Key 但未找到同业 | 跳过同业对比，返回 `peer_data_available: false`。前端隐藏同业表格。 |
| 数据完整 | 完整分析：当前乘数、历史百分位、同业偏差百分比对比。 |

### 配置

项目根目录新增 `.env` 文件（已被 git 忽略）：
```
AQ_FMP_API_KEY=<your-key>
```

### 代码质量修复（审核后）

v0.2.0 通过代码审核后修复了以下问题：

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `peer_comparison` dict 被就地修改 | HIGH | 改为展开运算符创建新对象 `{**peer_comparison, "deltas": deltas}` |
| relative_valuation 与 strategy 各自独立调用 FMP API | HIGH | strategy 优先从 relative_valuation_result 中读取 current_price 和 annual_prices，避免重复请求 |
| 所有 FMP API 方法静默吞掉异常 | HIGH | 改为精确捕获（`httpx.HTTPStatusError`、`httpx.RequestError`、`KeyError/ValueError/TypeError`）并记录 `logging.warning` |
| SSE 错误事件泄露内部异常信息 | HIGH | 前端只显示通用消息，完整异常通过 `logger.exception()` 记录到服务端 |
| `httpx.AsyncClient` 在模块导入时创建 | HIGH | 改为懒初始化，首次使用时创建 |
| FMP 历史行情依赖 API 排序但未验证 | MEDIUM | 显式 `sorted(data, key=lambda e: e["date"], reverse=True)` 排序 |
| 同业对比表目标行只显示 delta% | MEDIUM | 改为同时显示绝对乘数值和偏差百分比 |
| 文件行数超过 400 行建议上限 | MEDIUM | 提取 `relative_valuation_math.py`（纯计算函数），主节点从 422 行降至 251 行 |
| 旧节点（financial_health/dcf_model/logic_trace）泄露异常信息 | HIGH | 统一使用通用错误消息 + 服务端日志 |
| DCF 重算端点未校验参数可导致 ZeroDivisionError | HIGH | `DCFRecalculateRequest` 新增 `discount_rate > terminal_growth_rate` 校验 |
| FMP 同业 API 可能返回目标公司自身 | HIGH | `get_peers()` 过滤掉与目标相同的 ticker |

### 新增文件（审核后）

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/relative_valuation_math.py` | 纯计算函数（无 I/O）：`compute_current_multiples`、`compute_historical_multiples`、`percentile_rank` 等 |

---

## v0.1.0 — 初始版本

**日期：** 2026-04-17

### 概要

白盒 AI 投资研究系统的首个版本。从 SEC EDGAR 获取财务报告数据，通过 LangGraph 状态机执行多步骤价值分析，并经由 SSE 将推理过程和分析结果以 Generative UI 组件的形式实时推送到 Next.js 前端。

### 技术架构

- **后端：** Python / FastAPI / LangGraph / pydantic-settings
- **前端：** Next.js 16 / React / shadcn-ui / SSE

### 后端功能

- **SEC EDGAR 管线：** `TickerResolver` 将股票代码映射为 CIK，`SECClient` 从 EDGAR API 抓取数据（10次/秒限速），`sec_agent.py` 使用 XBRL 标签回退链对数据进行标准化处理。
- **财务健康节点：** 利息覆盖率、负债权益比、利润率（毛利率/营业利润率/净利率）、营收年复合增长率（3年/5年）、净资产收益率（ROE）、综合健康评级。
- **DCF 模型节点：** 自由现金流预测、终值计算、贴现率、每股内在价值。支持通过 `POST /api/recalculate-dcf` 用用户调节的参数重新计算。
- **策略节点：** 安全边际、P/E 百分位分析、入场信号（深度价值 / 低估 / 合理 / 高估）、建议入场价格。
- **逻辑溯源节点：** 将每个指标映射回其 SEC 文件来源，构建源文件 URL，生成最终分析结论。

### 前端功能

- 基于 SSE 的流式传输，使用 `useSSE` 和 `useAnalysisStream` 自定义 Hook
- 9 个通过组件注册表懒加载的分析组件
- 带打字机效果的 Agent 终端
- 显示管线步骤的进度追踪器
- DCF 假设滑块，支持实时重算

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analyze/{ticker}` | GET | SSE 流，触发完整 LangGraph 分析 |
| `/api/recalculate-dcf` | POST | 用用户调节的参数重新计算 DCF |

### LangGraph 管线

```
START → fetch_sec_data → [错误→END] → financial_health_scan → dynamic_dcf → strategy → logic_trace → END
```
