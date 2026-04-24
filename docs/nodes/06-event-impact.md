# Node 6: event_impact

> 图位置: `event_sentiment → event_impact → strategy`

## 职责

两步 LLM 分析：筛选对估值有实质影响的事件，分析对 DCF 参数的影响，应用调整并重算 DCF。将定性消息面转化为定量估值修正。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |
| `event_sentiment_result` | `dict \| None` | ⬜ | → [Node 5 输出](05-event-sentiment.md#event_sentiment_result-结构体); 缺失时跳过 |
| `dcf_result` | `dict \| None` | ⬜ | → [Node 3 输出](03-dcf-model.md#dcf_result-结构体); 缺失时跳过 |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.ticker` | `str` | ✅ | 日志 + LLM prompt |
| `financials.diluted_shares[-1].value` | `float \| None` | ⬜ | DCF 重算的 shares 参数 |
| `event_sentiment_result.articles` | `list[dict]` | ⬜ | 待分析文章列表; 空时跳过 |
| `dcf_result.assumptions` | `dict` | ⬜ | 原始 DCF 假设 (缺失时跳过) |
| `dcf_result.assumptions.growth_rate` | `float` | ⬜ | 增长率 (%) (默认 10.0) |
| `dcf_result.assumptions.terminal_growth_rate` | `float` | ⬜ | 永续增长率 (%) (默认 3.0) |
| `dcf_result.assumptions.discount_rate` | `float` | ⬜ | WACC (%) (默认 10.0) |
| `dcf_result.assumptions.latest_fcf` | `float` | ⬜ | 最新 FCF ($) (默认 0) |

### NVDA 示例 (输入子字段)

```json
{
  "financials": {
    "ticker": "NVDA",
    "diluted_shares": [{"calendar_year": 2024, "value": 2487000000}]
  },
  "event_sentiment_result": {
    "articles": [
      {"headline": "NVIDIA Reports Record Revenue of $60.9B", "source": "SEC EDGAR", "...": "..."},
      {"headline": "NVIDIA unveils Blackwell GPU", "source": "Reuters", "...": "..."}
    ]
  },
  "dcf_result": {
    "assumptions": {
      "growth_rate": 16.47,
      "terminal_growth_rate": 3.0,
      "discount_rate": 9.67,
      "latest_fcf": 26657000000
    }
  }
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_impact_result` | `dict \| None` | 事件影响分析结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `event_impact_result` 结构体

> **源码**: `backend/agents/nodes/event_impact.py` line 462-476

```python
{
    "ticker": str,
    "original_assumptions": {                       # 原始 DCF 假设
        "growth_rate": float,                       # (%)
        "terminal_growth_rate": float,              # (%)
        "discount_rate": float,                     # (%)
        "latest_fcf": float,                        # ($)
    },
    "parameter_adjustments": dict,                  # LLM 建议的调整 (结构见下)
    "adjusted_assumptions": {                       # 调整后的假设
        "growth_rate": float,                       # (%), 已 clamp 到 [-10, 30]
        "terminal_growth_rate": float,              # (%), 已 clamp 到 [0, 5]
        "discount_rate": float,                     # (%), 已 clamp 到 [5, 20]
        "latest_fcf": float,                        # ($)
    },
    "recalculated_dcf": dict,                       # 重算的 DCF 结果 (结构同 Node 3 dcf_result)
    "impactful_articles": [                         # 触发调整的文章
        {
            "headline": str,
            "source": str,
            "sentiment": float,
            "...": "...",                           # 原始文章字段
        },
    ],
    "summary": str,                                 # 一句话影响总结
    "confidence": float,                            # [0, 1] 置信度
}
```

### `parameter_adjustments` 子结构

LLM 返回的每个参数调整建议:

```python
{
    "growth_rate": {"type": "delta|multiplier|absolute", "value": float, "reasoning": str} | None,
    "terminal_growth_rate": ... | None,
    "discount_rate": ... | None,
    "risk_adjustment": ... | None,          # 附加到 discount_rate
    "revenue_adjustment": ... | None,       # 增长率乘数
    "margin_adjustment": ... | None,        # 利润率→增长率 × 0.5
    "fcf_one_time_adjust": ... | None,      # FCF 一次性替换
}
```

### PARAMETER_REGISTRY (调整边界)

| 参数 | 调整方式 | min | max | 说明 |
|------|----------|-----|-----|------|
| `growth_rate` | delta | -10% | 30% | 收入增长率 |
| `terminal_growth_rate` | delta | 0% | 5% | 永续增长率 |
| `discount_rate` | delta | 5% | 20% | WACC |
| `risk_adjustment` | delta | -5% | 10% | WACC 附加 |
| `revenue_adjustment` | multiplier | 0.5 | 1.5 | 增长率乘数 |
| `margin_adjustment` | delta × 0.5 | -10% | 10% | 利润率→增长率 |
| `fcf_one_time_adjust` | absolute | -∞ | +∞ | FCF 一次性 |

### NVDA 示例 (输出)

```json
{
  "event_impact_result": {
    "ticker": "NVDA",
    "original_assumptions": {
      "growth_rate": 16.47,
      "terminal_growth_rate": 3.0,
      "discount_rate": 9.67,
      "latest_fcf": 26657000000
    },
    "parameter_adjustments": {
      "growth_rate": {"type": "delta", "value": 3.0, "reasoning": "AI datacenter demand acceleration"},
      "discount_rate": {"type": "delta", "value": -0.5, "reasoning": "Reduced competitive risk from dominant market position"},
      "terminal_growth_rate": null,
      "risk_adjustment": null,
      "revenue_adjustment": null,
      "margin_adjustment": null,
      "fcf_one_time_adjust": null
    },
    "adjusted_assumptions": {
      "growth_rate": 19.47,
      "terminal_growth_rate": 3.0,
      "discount_rate": 9.17,
      "latest_fcf": 26657000000
    },
    "recalculated_dcf": {
      "projected_fcf": [{"year": 1, "fcf": 31847000000, "...": "..."}],
      "terminal_value": 1704150000000,
      "terminal_pv": 708720000000,
      "pv_fcf_sum": 400340000000,
      "enterprise_value": 1109060000000,
      "intrinsic_value_per_share": 445.94,
      "assumptions": {"growth_rate": 19.47, "terminal_growth_rate": 3.0, "discount_rate": 9.17, "projection_years": 10, "latest_fcf": 26657000000}
    },
    "impactful_articles": [
      {"headline": "NVIDIA Reports Record Revenue of $60.9B", "source": "SEC EDGAR"},
      {"headline": "NVIDIA unveils Blackwell GPU architecture", "source": "Reuters"}
    ],
    "summary": "AI demand surge and Blackwell GPU launch support sustained above-trend growth",
    "confidence": 0.75
  },
  "reasoning_steps": [
    "Original DCF assumptions: growth=16.5%, terminal=3.0%, WACC=9.67%, FCF=$26,657,000,000",
    "LLM identified 2 impactful articles: Record earnings and Blackwell GPU launch",
    "Adjusted assumptions: growth=19.5%, terminal=3.0%, WACC=9.17%, FCF=$26,657,000,000",
    "Recalculated intrinsic value: $445.94/share",
    "Impact analysis summary: AI demand surge and Blackwell GPU launch support sustained above-trend growth",
    "Confidence: 75%"
  ]
}
```

## 核心算法

```
1. 提取原始 DCF 假设: {growth_rate, terminal_growth, discount_rate, latest_fcf}

2. LLM Call 1 — 筛选: 从 articles 中筛选对估值有实质影响的事件
   └── 排除: 常规分析师评级、泛市场评论、已定价业绩报告
   └── 无影响 → return None

3. LLM Call 2 — 分析: 对筛选后文章分析参数影响
   └── 可调参数见 PARAMETER_REGISTRY (7 个)

4. 应用调整 (event_impact_math.py):
   ├── delta → 累加; multiplier → 相乘; absolute → 替换
   └── clamp 到 PARAMETER_REGISTRY min/max

5. DCF 重算: recalculate_dcf() → 调用 dcf_model.compute_dcf()
```

## 关键假设

- 两步 LLM（先筛选再分析）比单步分析更准确、更可控
- 保守原则：LLM 仅建议高置信度调整
- 7 个可调参数覆盖了新闻对 DCF 的主要影响路径
- URL 校验: LLM base URL 必须 HTTPS 或 localhost（防 SSRF）

## LLM 使用

| 调用 | 模型 | 用途 |
|------|------|------|
| `_FILTER_SYSTEM_PROMPT` | DeepSeek | 筛选有估值影响的新闻 |
| `_ANALYSIS_SYSTEM_PROMPT` | DeepSeek | 分析参数调整方向和幅度 |

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| 任一前提数据缺失 | 节点跳过, 不阻塞 |
| LLM API Key 未设置 | 节点跳过 |
| LLM 不可用 | 节点跳过 |
| 无重大事件 | return None ("no material events found") |
| **最终效果** | **Node 7 使用原始 DCF 值 (无事件修正)** |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/event_impact.py` | 节点入口 + LLM 调用 |
| `backend/agents/nodes/event_impact_math.py` | PARAMETER_REGISTRY + 调整逻辑 + DCF 重算 |

## 与其他节点的关系

- **依赖**: `event_sentiment` (文章), `dcf_model` (原始假设 + `compute_dcf()`)
- **消费者**: `strategy` 优先使用 `recalculated_dcf.intrinsic_value_per_share`

## 前端组件

| component_type | 组件 |
|----------------|------|
| `event_impact_card` | `EventImpactCard` — 参数调整对比 + 重算 DCF 结果 |
