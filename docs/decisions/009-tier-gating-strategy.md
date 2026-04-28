# ADR 009: Tier Gating at Node Entry, Not at Route Layer

**状态**: 已采纳
**日期**: 2026-04-25 (v0.7.0, Phase 2)
**影响节点**: investment_thesis, qualitative_analysis, risk_yoy_diff, moat_analysis
**相关代码**: `backend/agents/nodes/_pro_gate.py`, `backend/api/routes.py`, `frontend/src/components/analysis/pro-locked-card.tsx`

## 背景

4 个 LLM Pro 节点要按 `user.tier ∈ {free, pro, admin}` 分级访问。两条主流路径，权衡点完全相反：

- 路由层门控：`/api/analyze` 直接 `Depends(require_pro)` 拒绝 free
- 节点层门控：路由全员通过，每个 Pro 节点开头 short-circuit

这是一个产品决策，不只是工程决策。

## 考虑的方案

### 方案 A: 路由层门控 — `/api/analyze` 加 `Depends(require_pro)`
- 实现一行代码
- 问题：**free 用户看不到任何东西**（包括 7 个数值节点）→ 失去免费工具的拉新价值
- 问题：用户体验"全或无"，转化率结构差（用户没尝过 Pro 价值就被挡）
- 问题：违反产品定位（"白盒可信的 DCF 分析" 是公开宣传，不该挡用户）

### 方案 B: 路由层细分两个 endpoint — `/analyze`（free）+ `/analyze/pro`（pro）
- 数据流分叉，前端要决策走哪个
- 问题：业务逻辑重复，graph 要 build 两套
- 问题：节点配置漂移风险

### 方案 C: 节点层门控 + 锁定预览卡 ✓
- 路由全员通过，所有 12 节点都跑（free 跑 7 个，4 个 Pro 节点 emit 预览卡 + 0 LLM 调用）
- free 用户能看到完整框架（DCF / 估值 / 财务健康 / 信号），有真实价值
- Pro 节点的"被锁"很可见（带 Upgrade CTA + 部分免费 preview 数据）→ 成为天然转化漏斗
- 路由层零变更，每个 Pro 节点 5 行 short-circuit 代码

### 方案 D: 在 LLM Client 里门控
- 任何 Pro task_tag 调用前检查 user_tier
- 问题：LLM Client 是基础设施，不该有业务概念（哪些 task 是 Pro 是策略，会变）
- 问题：拒绝时机晚 — 节点已经做了 SEC fetch / parse，浪费 IO

## 决策

采用方案 C。

### 实现：`_pro_gate.py` 共享 helper

```python
# 4 个 Pro 节点开头都这样写
if not is_pro_user(state):
    return emit_lock(
        writer=writer,
        node_name="moat_analysis",
        feature_label="Moat / 7 Powers scoring",
        locked_component_type="moat_locked_card",
        state_field="moat_result",
        ticker=financials.ticker,
        entity_name=financials.entity_name,
    ).payload   # → {"moat_result": None, "reasoning_steps": ["...gated..."]}
```

`emit_lock(...)` 推 3 条 SSE：
1. `agent_thinking`（"This is a Pro feature. Skipping for free tier."）
2. `component`（`*_locked_card` 携带 feature_label 和可选预览数据）
3. `step_complete`

### 用户身份注入路径

```
api/routes.py /analyze:
  ↓ Depends(get_optional_user)        ← 匿名通过, user=None
  ↓ user_tier = user.tier if user else "free"
  ↓ initial_state["user_tier"] = user_tier
  ↓ LangGraph 跑 12 节点
      └── 4 Pro 节点开头 is_pro_user(state) 短路
```

**关键性质**：tier 从 DB 实时读取（[ADR 008](008-pluggable-auth-providers.md)），admin 升降级 → 用户下次请求**立即**生效，无需重新登录。

### 锁定预览的 4 个 component_type

每个 Pro 节点 emit 自己的 `*_locked_card`，前端 registry 全部映射到同一个 React 组件 `pro-locked-card.tsx`：

```ts
// frontend/src/components/component-registry.ts
investment_thesis_locked_card: lazy(() => import("./analysis/pro-locked-card")),
qualitative_locked_card:        lazy(() => import("./analysis/pro-locked-card")),
risk_yoy_diff_locked_card:      lazy(() => import("./analysis/pro-locked-card")),
moat_locked_card:               lazy(() => import("./analysis/pro-locked-card")),
```

后端注入 `feature_label` 给组件，文案差异化由 props 驱动而非组件树。

### 免费预览的"钩子"信息

`investment_thesis_locked_card` 携带 `strategy_result.signal` 和 `margin_of_safety_pct` —— 免费用户能看到"Overvalued / -61%"这样的硬数字结论，但看不到完整论点。这是**最强的转化钩子**：用户看到"被高估 61%"会想知道为什么 → 升级。

## 后果

**正面**:
- Free 用户得到真实有价值的产品（7 节点全部能用），没被坑
- Pro 价值在用户面前可见但锁住 → 自然漏斗
- 路由层零业务感知，添加 Pro 节点不改路由
- LLM 0 调用成本（节点 short-circuit 在所有外部 IO 之前）
- 测试简单：mock state["user_tier"] 即可单测每个分支

**负面**:
- 节点必须显式调 `is_pro_user(state)` —— 漏掉就成了"Pro 功能免费送"（缓解：所有 Pro 节点的开头是模板代码 + code review checklist）
- 4 个 Pro 节点开头都有同样 5 行（缓解：抽 `_pro_gate.emit_lock(...)` helper, 无重复逻辑）
- 前端要为每个 Pro 节点准备 locked card 文案 / 预览（缓解：单一组件 + 后端注入 feature_label, 文案在一处）

**降级行为**:

| 场景 | Free 用户看到 | Pro 用户看到 |
|------|--------------|-------------|
| 主流 happy path | 7 节点输出 + 4 个 locked card | 12 节点全部输出 |
| LLM 未配置 | 7 节点 + 4 个 locked card（locked 优先于 LLM check） | 7 节点 + 4 个 "LLM not configured" skip event |
| 某个 Pro 节点 LLM 失败 | 不受影响（永远是 locked） | 7 节点 + 3 Pro 卡片 + 1 个 "LLM error" skip event |

**未决问题**:
- [ ] 限流是否按 tier 区分（free 3/day, Pro 50/day）—— 当前都按 IP 默认 3/day，Pro 用户应该有更高额度（follow-up）
- [ ] tier=admin 的具体含义未定义 —— 当前等同于 pro，未来可能加"绕过 budget gate"等特权
- [ ] 锁定预览的"钩子"数据要不要随 Pro 节点的能力升级而变更（e.g. moat_locked_card 也带 overall_moat_score 数字预览？）
