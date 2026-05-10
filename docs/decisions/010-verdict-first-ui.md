# ADR 010: Verdict-First UI

**状态**: 已采纳
**日期**: 2026-05-01
**影响范围**: frontend canvas / conversation panel / analysis layout
**相关代码**: `frontend/src/components/canvas/`, `frontend/src/components/conversation-panel.tsx`, `frontend/src/components/layout/app-shell.tsx`

## 背景

v0.7 之后，分析结果会产生 19 张左右的卡片。旧 canvas 采用纵向堆叠，用户需要在 4000-6000px 的长列中滚动才能找到结论、估值、风险和来源。推理链也留在左侧 conversation 中，使"答案"和"过程"混在一起。

v0.8 的目标是把结果页改成 verdict-first：先给可扫读结论，再让用户按任务进入估值、策略、风险、来源等分区。

## 考虑的方案

### 方案 A: 保持单列堆叠

- 实现成本最低。
- 问题：卡片数量增长后，首屏无法体现投资结论。
- 问题：Pro 节点和后续留存功能会继续增加信息量，长列会越来越难用。

### 方案 B: 自动跳转到最新卡片所在 tab

- 新卡片到达时看起来更"实时"。
- 问题：流式过程中抢焦点，用户正在阅读的内容会被打断。

### 方案 C: Sticky Verdict Hero + 5 Tabs + 非抢焦点提示 ✓

- 首屏固定展示核心结论。
- 详细卡片按用户任务分组。
- 新卡片到达非活动 tab 时只显示 pulse dot，不自动切换。

## 决策

采用方案 C。

信息架构分为 5 个 tab：

- `Verdict`: `investment_thesis_card`, `qualitative_insights_card`, `strategy_dashboard`
- `Valuation`: DCF、gauge、assumption slider、FCF/revenue chart、relative valuation、metric table、financial health
- `Strategy`: sentiment、event impact
- `Risks & Moat`: risk factors、risk yoy diff、moat
- `Sources`: source table + per-node reasoning trace

Tab 映射由 `frontend/src/components/canvas/tab-groups.ts` 维护，作为单一来源。

Hero 通过 `deriveHero(components)` 从已到达的 `ComponentInstruction[]` 派生字段，不重新计算业务结果：

- signal 优先取 `investment_thesis_card.recommendation`，fallback 到 `strategy_dashboard.signal`
- MoS、upside、current price、intrinsic value、entry price 来自 `strategy_dashboard`
- confidence、headline 来自 `investment_thesis_card`
- high severity risk count 来自 `risk_factors_card.top_risks`

Conversation panel 改为状态机：

```text
idle -> streaming -> collapsed rail -> expanded overlay -> rail
```

`overlayOpen` 是唯一用户驱动状态；streaming / rail / overlay 由 `displayStatus` 和 ticker 派生。

## 后果

**正面**:

- 首屏能快速回答"这个标的是不是有吸引力"。
- 卡片按任务分区后，用户不需要扫完整长列。
- Tab 不自动切换，保留流式反馈但不抢焦点。
- `CanvasTabs` 用 `seenCounts` lazy-init，缓存视图不会出现假的新卡提示。

**负面**:

- 前端状态边界更复杂，`activeTab`、pulse dot、conversation rail 都需要清晰 ownership。
- Hero 是摘要，不是新计算源；后续新增卡片若要影响 hero，必须显式扩展 `deriveHero`。

**缓解措施**:

- 使用 `tab-groups.ts` 管理分组。
- 历史切换时通过 `<AnalysisCanvas key={activeEntryId}>` 重置内部 tab 状态。
- 推理 trace 移入 Sources tab，保持左侧 conversation 专注当前交互。
