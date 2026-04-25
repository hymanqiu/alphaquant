# Node 7: strategy

> 图位置: `event_impact → strategy → logic_trace`

## 职责

综合 DCF 内在价值、实时价格、相对估值、情绪修正，计算安全边际和历史 P/E 分位数，给出买入信号。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |
| `dcf_result` | `dict \| None` | ⬜ | → [Node 3 输出](03-dcf-model.md#dcf_result-结构体); 缺失时跳过 |
| `relative_valuation_result` | `dict \| None` | ⬜ | → [Node 4 输出](04-relative-valuation.md#relative_valuation_result-结构体) |
| `event_sentiment_result` | `dict \| None` | ⬜ | → [Node 5 输出](05-event-sentiment.md#event_sentiment_result-结构体) |
| `event_impact_result` | `dict \| None` | ⬜ | → [Node 6 输出](06-event-impact.md#event_impact_result-结构体) |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.ticker` | `str` | ✅ | API 参数 + UI |
| `financials.entity_name` | `str` | ✅ | UI 显示 |
| `financials.diluted_eps` | `list[AnnualMetric]` | ⬜ | P/E 计算 (EPS > 0 时) |
| `dcf_result.intrinsic_value_per_share` | `float` | ✅ | 原始内在价值 |
| `event_impact_result.recalculated_dcf.intrinsic_value_per_share` | `float` | ⬜ | 优先使用的事件调整后价值 |
| `relative_valuation_result.price_available` | `bool` | ⬜ | 是否有价格数据 |
| `relative_valuation_result.current_price` | `float` | ⬜ | 复用价格 (避免重复 API) |
| `relative_valuation_result.annual_prices` | `dict[int, float]` | ⬜ | P/E 分位数的年终价格 |
| `relative_valuation_result.peer_comparison.peer_data_available` | `bool` | ⬜ | 同业数据是否可用 (守卫) |
| `relative_valuation_result.peer_comparison.deltas.pe` | `float \| None` | ⬜ | 同业 P/E 偏差 (%) |
| `event_sentiment_result.sentiment_adjustment.margin_of_safety_pct_delta` | `int` | ⬜ | MoS 修正量 (%) |
| `event_sentiment_result.sentiment_adjustment.reasoning` | `str` | ⬜ | 修正理由 |
| `event_sentiment_result.sentiment_label` | `str` | ⬜ | 情绪标签 |

> **内在价值优先级**: event_impact 的重算值 > dcf_result 的原始值

### NVDA 示例 (输入子字段)

```json
{
  "financials": {
    "ticker": "NVDA",
    "entity_name": "NVIDIA Corp",
    "diluted_eps": [
      {"calendar_year": 2021, "value": 3.21},
      {"calendar_year": 2022, "value": 3.34},
      {"calendar_year": 2023, "value": 3.62},
      {"calendar_year": 2024, "value": 12.06}
    ]
  },
  "dcf_result": {
    "intrinsic_value_per_share": 347.99
  },
  "event_impact_result": {
    "recalculated_dcf": {"intrinsic_value_per_share": 445.94}
  },
  "relative_valuation_result": {
    "price_available": true,
    "current_price": 880.00,
    "annual_prices": {2021: 294.0, 2022: 146.0, 2023: 495.0, 2024: 880.0},
    "peer_comparison": {"deltas": {"pe": 155.9}}
  },
  "event_sentiment_result": {
    "sentiment_label": "Bullish",
    "sentiment_adjustment": {"margin_of_safety_pct_delta": 3, "reasoning": "Bullish sentiment"}
  }
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `strategy_result` | `dict \| None` | 策略分析结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `strategy_result` 结构体

> **源码**: `backend/agents/nodes/strategy.py` line 232-244

```python
{
    "current_price": float,                         # 实时价格 ($)
    "intrinsic_value": float,                       # 内在价值 ($/股)
    "margin_of_safety_pct": float,                  # 安全边际 (%), rounded to 1 decimal
    "suggested_entry_price": float,                 # 建议买入价 = intrinsic × 0.85 ($)
    "upside_pct": float,                            # 潜在涨幅 (%), rounded to 1 decimal
    "signal": str,                                  # "Deep Value" | "Undervalued" | "Fair Value" | "Overvalued"
    "current_pe": float | None,                     # 当前 P/E (EPS > 0 时)
    "pe_percentile": float | None,                  # P/E 历史百分位 (需 ≥3 年数据), 0-100
    "historical_pe": [                              # 历史 P/E (可能为 None)
        {"year": int, "pe": float},
    ] | None,
    "sentiment_delta": float,                       # 情绪修正量 (%)
    "sentiment_note": str,                          # 修正理由
}
```

### Signal 判定阈值

| `margin_of_safety_pct` | Signal |
|:---:|---|
| > 25% | Deep Value |
| > 10% | Undervalued |
| > -10% | Fair Value |
| ≤ -10% | Overvalued |

> **计算**: `mos_pct = (intrinsic - price) / intrinsic × 100`
> **建议买入价**: `intrinsic × 0.85` (固定 15% 折扣)

### NVDA 示例 (输出)

```json
{
  "strategy_result": {
    "current_price": 880.00,
    "intrinsic_value": 445.94,
    "margin_of_safety_pct": -97.3,
    "suggested_entry_price": 379.05,
    "upside_pct": -49.3,
    "signal": "Overvalued",
    "current_pe": 72.97,
    "pe_percentile": 100.0,
    "historical_pe": [
      {"year": 2021, "pe": 91.6},
      {"year": 2022, "pe": 43.7},
      {"year": 2023, "pe": 136.7},
      {"year": 2024, "pe": 72.97}
    ],
    "sentiment_delta": 3.0,
    "sentiment_note": "Bullish sentiment"
  },
  "reasoning_steps": [
    "Using event-impact-adjusted DCF intrinsic value",
    "Current market price: $880.00",
    "Margin of safety: -97.3%",
    "Signal: Overvalued",
    "Current P/E: 72.97",
    "P/E at 100th percentile over 4 years",
    "Relative valuation: P/E significantly above peers — valuation premium warrants caution.",
    "Sentiment adjustment: Bullish sentiment (Δ+3%)",
    "Adjusted MoS: -94.3%"
  ]
}
```

## 核心算法

```
1. 选择内在价值:
   ├── 优先: event_impact_result.recalculated_dcf.intrinsic_value_per_share
   └── 回退: dcf_result.intrinsic_value_per_share

2. 获取实时价格: FMP /stable/quote
   ├── 优先复用 relative_valuation_result.current_price
   └── 回退: market_data_client.get_current_price(ticker)

3. 安全边际 (Margin of Safety):
   ├── mos_pct = (intrinsic - price) / intrinsic × 100
   ├── suggested_entry = intrinsic × 0.85
   ├── upside_pct = (intrinsic - price) / price × 100
   └── signal: 见上方阈值表

4. P/E 历史分位数 (10 年):
   ├── 年终股价 × SEC EPS → 每年 P/E (仅 EPS > 0)
   └── percentile_rank(current_pe, historical_pe) (需 ≥ 3 年)

5. 相对估值交叉校验:
   ├── 同业 P/E 偏差 < -20% → "支持低估"
   ├── 同业 P/E 偏差 > +20% → "估值溢价"
   └── else → "大致一致"

6. 情绪修正 (两层调整叠加):
   ├── event_impact: 基本面影响 → 新 intrinsic
   ├── event_sentiment: 市场情绪 → MoS delta
   └── 最终: adjusted_mos = mos + delta
```

## 关键假设

- **FMP /stable/ API** → [ADR 005](../decisions/005-fmp-stable-api.md)
- 安全边际信号阈值固定 (25%/10%/-10%)，未按行业调整
- 两层调整叠加设计: event_impact 改内在价值，sentiment 改安全边际，互不冲突
- P/E 使用 raw close + raw EPS（对股票拆分不变）
- 15% 建议买入价折扣是固定假设

## 失败模式与降级

| 场景 | 处理 |
|------|------|
| DCF 不可用或 intrinsic = None | 跳过 (不阻塞) |
| 市场价格获取失败 | 跳过 (不阻塞) |
| EPS 为负 (亏损公司) | P/E 分位数跳过 |
| relative_valuation_result 为 None | 跳过同业校验 |
| event_sentiment_result 为 None | delta=0, 无情绪修正 |
| 通用异常 | `ErrorEvent(recoverable=True)` → 不阻塞 logic_trace |

## 源文件

`backend/agents/nodes/strategy.py` — 计算 + FMP 调用

## 配置依赖

| 环境变量 | 必需 | 说明 |
|----------|------|------|
| `AQ_FMP_API_KEY` | 可选 | 无 Key → strategy 跳过 |

## 前端组件

| component_type | 组件 |
|----------------|------|
| `strategy_dashboard` | `StrategyDashboard` — 信号徽章 + 价格对比 + 温度计 + P/E 进度条 + 买入建议 |

**前端重算**: 用户拖动 DCF 滑块时，strategy_dashboard 在前端直接重算安全边际/信号（阈值与后端一致），无需请求后端。
