# Node 12: investment_thesis 🔒 Pro

> 图位置: `moat_analysis → investment_thesis → logic_trace`

## 职责

汇总全部上游节点结果（DCF / 估值信号 / 财务健康 / 情绪 / 事件影响 / 定性分析 / YoY diff / 护城河），用 LLM 合成一份**结构化研报**：核心论点 + 看多 / 看空 / 风险点 + 操作建议 + 推荐评级 + 置信度。这是面向"客户能直接读"的最终交付物，也是 Pro 订阅最直接的价值锚点。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段（全部上游结果都会读）

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | 取 ticker + entity_name |
| `user_tier` | `str` | ✅ | `"free"` 短路 emit locked card |
| `strategy_result` | `dict` | ✅ | 没有 strategy 就不能写 thesis（margin of safety / signal 是论点骨架） |
| `dcf_result` | `dict \| None` | ⬜ | DCF 假设 |
| `relative_valuation_result` | `dict \| None` | ⬜ | 同业对比 |
| `event_sentiment_result` | `dict \| None` | ⬜ | 新闻情绪 |
| `event_impact_result` | `dict \| None` | ⬜ | 调整后的 DCF |
| `qualitative_result` | `dict \| None` | ⬜ | MD&A + Risk Factors（[Node 9](09-qualitative-analysis.md)） |
| `risk_yoy_diff_result` | `dict \| None` | ⬜ | YoY 风险变化（[Node 10](10-risk-yoy-diff.md)） |
| `moat_result` | `dict \| None` | ⬜ | 7 Powers 评分（[Node 11](11-moat-analysis.md)） |

### 子字段访问（被 `_build_variables` 读出格式化）

| Helper 函数 | 读什么 | 写到 prompt 哪个 placeholder |
|------------|--------|-----|
| `_dcf_summary(dcf, event_impact)` | DCF + 事件调整后的 DCF | `{dcf_summary}` |
| `_relative_valuation_summary(rel_val)` | peer P/E 折价 | `{relative_valuation_summary}` |
| `_financial_health_summary(state)` | health_metrics + assessment | `{financial_health_summary}` |
| `_event_sentiment_summary(sent)` | overall_score + key_events | `{event_sentiment_summary}` |
| `_event_impact_summary(ei)` | parameter_adjustments | `{event_impact_summary}` |
| `_qualitative_summary(qual)` | mdna.tone + 增长驱动 + 担忧 + risk_factors.top_risks + concentration | `{qualitative_summary}` |
| `_risk_yoy_summary(yoy)` | 4 桶 diff 标题列表 | `{risk_yoy_summary}` |
| `_moat_summary(moat)` | classification + primary_powers + power 评分 | `{moat_summary}` |

每个 helper 都做 None-safe 降级（缺少上游 → 写 "not available"）。

### AAPL 示例 (输入子字段, 摘要)

```json
{
  "user_tier": "pro",
  "financials": {"ticker": "AAPL", "entity_name": "Apple Inc."},
  "strategy_result": {
    "current_price": 273.43, "intrinsic_value": 169.41,
    "margin_of_safety_pct": -61.4, "signal": "Overvalued",
    "current_pe": 36.7, "pe_percentile": 80.0
  },
  "qualitative_result": {"mdna": {"tone": "cautious"}, "risk_factors": {"top_risks": [...]}},
  "moat_result": {"moat_classification": "wide", "overall_moat_score": 9.0}
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `investment_thesis_result` | `dict \| None` | 结构化研报 |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `investment_thesis_result` 结构体

> **源码**: `backend/agents/nodes/investment_thesis.py` line 263-271 (`InvestmentThesis` Pydantic)

```python
{
    "thesis_headline": str,                 # 一句话核心观点 (≤25 词)
    "recommendation": "Strong Buy" | "Buy" | "Hold" | "Reduce" | "Sell",
    "bull_points": list[str],               # 3-5 条看多
    "bear_points": list[str],               # 3-5 条看空（可空）
    "key_risks": list[str],                 # 3-5 条关键风险
    "action_summary": str,                  # 2-3 句操作建议
    "confidence": float,                    # [0, 1]
}
```

**`recommendation` 选择规则** (prompt 内强制):

| 推荐 | margin of safety 区间 | 附加条件 |
|------|----------------------|---------|
| Strong Buy | > 25% | + 财务健康 |
| Buy | 10% — 25% | — |
| Hold | -10% — 10% | — |
| Reduce | -25% — -10% | — |
| Sell | < -25% | OR 重大 red flags |

### AAPL 示例 (LLM 模拟输出, 真实数据 + Overvalued 信号)

```json
{
  "investment_thesis_result": {
    "thesis_headline": "Wide-moat brand and ecosystem stickiness justify a premium, but a 61% gap between price and DCF intrinsic value makes near-term entry unattractive.",
    "recommendation": "Reduce",
    "bull_points": [
      "Wide moat classification (overall 9.0/10) anchored in dominant brand power and ecosystem switching costs",
      "Services revenue growth across App Store, cloud, and financial services drives recurring revenue",
      "Net margin of 26.9% supports premium valuation in a maturing industry"
    ],
    "bear_points": [
      "Current price $273.43 vs DCF intrinsic $169.41 implies -61.4% margin of safety",
      "Current P/E 36.7 sits at 80th percentile of 10-year history (historically expensive)",
      "Management tone in 2025 MD&A is cautious; flags FX and regulatory headwinds explicitly"
    ],
    "key_risks": [
      "DMA / antitrust enforcement could force material business model changes",
      "Concentrated supplier exposure in Asia (geopolitical risk)",
      "Foreign-exchange headwinds compressing reported revenue"
    ],
    "action_summary": "Wait for a pullback to the suggested entry price of $144.00 (15% margin of safety). Existing holders may consider trimming exposure given current overvaluation and historically rich P/E.",
    "confidence": 0.74
  }
}
```

## 核心算法

```
1. is_pro_user(state) → False → emit investment_thesis_locked_card → return None
   (locked card 携带 strategy_result.signal + margin_of_safety_pct 作为免费预览)

2. is_llm_configured() → False → emit skipped → return None

3. financials 或 strategy_result 缺失 → emit skipped → return None
   (没有 strategy 的 thesis 就是空中楼阁)

4. variables = _build_variables(state)
   ├── 主 strategy 数值 → format 成美元/百分比字符串
   └── 8 个 helper 函数把上游 dict 格式化成 thesis prompt 的 placeholder

5. LLMClient.complete_json("investment_thesis", response_model=InvestmentThesis,
                            task_tag="thesis")
   └── task_tag="thesis" 触发 narrative provider 路由（如配了 GPT-4o / Claude）

6. emit ComponentEvent("investment_thesis_card", props={ticker, entity_name, ...thesis})
```

## 关键假设

- **thesis 是综合产出，不是源数据**：所有数值已经在上游验证过；thesis 只做"用人话讲"的工作
- 上游缺失某些字段是常态（FMP 402、Finnhub 空、10-K 解析失败），prompt 必须能处理 "not available"
- `task_tag="thesis"` 是路由到 narrative provider 的关键钩子（[ADR 006](../decisions/006-unified-llm-client.md)）—— admin 可以单独把这一条切到 GPT-4o 而其它任务保持 DeepSeek
- recommendation 严格按 margin of safety 区间映射，**不让 LLM 自由发挥** —— 防止"看多 narrative + Sell 推荐"这种自相矛盾
- 免费用户能在 locked card 看到 `signal` + `margin_of_safety_pct`（preview），但看不到 thesis 内容 —— 是 Upgrade 的天然钩子

## LLM 使用

| 调用 | task_tag | Prompt | 输入 | 输出 |
|------|----------|--------|------|------|
| 投资论点合成 | `thesis` | `prompts/investment_thesis_v1.yaml` | ticker + 8 个 helper 输出的格式化字符串 | `InvestmentThesis` (Pydantic) |

**单次成本**: ~2K input + ~1K output = **~$0.0008 DeepSeek / ~$0.02 GPT-4o**。

`task_tag="thesis"` 路由到 narrative provider —— 如果 admin 配了 `AQ_LLM_NARRATIVE_*`，这个调用会走那个 provider 而非 primary。

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| `user_tier="free"` | emit `investment_thesis_locked_card` (含 strategy preview), 返回 None |
| `financials` 或 `strategy_result` 缺失 | emit skipped, 返回 None |
| LLM 未配置 | emit skipped, 返回 None |
| LLM 调用失败 (402 / parse / budget) | emit skipped + thinking event, 返回 None |
| 上游 4 个 Pro 节点全部失败 (qualitative / yoy / moat 都 None) | 仍能跑 —— prompt 用 "not available" 占位 |
| **下游影响** | `logic_trace` 不依赖 thesis, 正常完成 |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/investment_thesis.py` | 节点入口 + InvestmentThesis Pydantic + 8 个 `_*_summary` helper |
| `backend/agents/nodes/_pro_gate.py` | tier 门控 helper |
| `backend/services/llm/client.py` | `LLMClient.complete_json` + `_select_provider("thesis")` 路由 |
| `backend/prompts/investment_thesis_v1.yaml` | thesis 合成 prompt（recommendation 映射规则也在这里） |

## 与其他节点的关系

- **依赖**: `strategy` (硬依赖); `dcf_model` / `relative_valuation` / `event_sentiment` / `event_impact` / `qualitative_analysis` / `risk_yoy_diff` / `moat_analysis` (软依赖, 缺失时降级)
- **消费者**: `logic_trace` 读 `investment_thesis_result.thesis_headline` 写入最终 verdict（如有）；前端 `strategy_dashboard` 旁边渲染 `investment_thesis_card`

## 前端组件

| component_type | 组件 | 触发条件 |
|----------------|------|----------|
| `investment_thesis_card` | `InvestmentThesisCard` — Bull/Bear/Risks 三栏 + recommendation 徽章 + confidence + action callout | 节点成功输出 |
| `investment_thesis_locked_card` | `ProLockedCard` (shared) — 带 strategy.signal + margin_of_safety_pct 的免费预览 + Upgrade CTA | `user_tier="free"` |

## 相关 ADR

- [009 — tier-gating-strategy](../decisions/009-tier-gating-strategy.md)
- [006 — unified-llm-client](../decisions/006-unified-llm-client.md)（特别是 narrative provider 路由）
