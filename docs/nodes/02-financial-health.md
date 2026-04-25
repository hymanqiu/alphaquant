# Node 2: financial_health_scan

> 图位置: `fetch_sec_data → financial_health_scan → dynamic_dcf`

## 职责

计算公司财务健康指标（利息覆盖率、债务/权益比、利润率时间序列、收入 CAGR、ROE）并给出综合评估。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |

### 子字段访问

节点实际从 `financials` 访问以下子字段 (`_run_financial_health`, line 94):

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.entity_name` | `str` | ✅ | UI 显示 |
| `financials.ticker` | `str` | ✅ | 日志 |
| `financials.operating_income` | `list[AnnualMetric]` | ✅ | 利息覆盖率分子 + 营业利润率 |
| `financials.interest_expense` | `list[AnnualMetric]` | ✅ | 利息覆盖率分母 |
| `financials.total_liabilities` | `list[AnnualMetric]` | ✅ | 债务/权益比分子 |
| `financials.stockholders_equity` | `list[AnnualMetric]` | ✅ | D/E 分母 + ROE 分母 |
| `financials.revenue` | `list[AnnualMetric]` | ✅ | CAGR 计算 + 利润率分母 |
| `financials.cost_of_revenue` | `list[AnnualMetric]` | ✅ | 毛利率 |
| `financials.net_income` | `list[AnnualMetric]` | ✅ | 净利润率 + ROE 分子 |

> 所有 `list[AnnualMetric]` 访问最新一年值: `field[-1].value`。数据缺失时对应指标返回 `None`。

### NVDA 示例 (输入子字段)

```json
{
  "entity_name": "NVIDIA Corp",
  "ticker": "NVDA",
  "operating_income":  [{"calendar_year": 2024, "value": 35577000000}],
  "interest_expense":  [{"calendar_year": 2024, "value": 247000000}],
  "total_liabilities": [{"calendar_year": 2024, "value": 22149000000}],
  "stockholders_equity": [{"calendar_year": 2024, "value": 43585000000}],
  "revenue": [
    {"calendar_year": 2021, "value": 26914000000},
    {"calendar_year": 2022, "value": 26974000000},
    {"calendar_year": 2023, "value": 26974000000},
    {"calendar_year": 2024, "value": 60922000000}
  ],
  "cost_of_revenue": [{"calendar_year": 2024, "value": 11622000000}],
  "net_income": [{"calendar_year": 2024, "value": 29760000000}]
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `health_metrics` | `dict \| None` | 各项健康指标值 |
| `health_assessment` | `str \| None` | 综合评估: `"Strong"` / `"Moderate"` / `"Weak"` |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `health_metrics` 结构体

> **源码**: `backend/agents/nodes/financial_health.py` line 100-163

```python
{
    "interest_coverage_ratio": float | None,    # operating_income / |interest_expense|
    "debt_to_equity": float | None,             # total_liabilities / stockholders_equity
    "roe": float | None,                        # (net_income / equity) × 100 (%)
    "revenue_cagr_3yr": float | None,           # 3 年收入 CAGR (%), 需 ≥4 年数据
    "revenue_cagr_5yr": float | None,           # 5 年收入 CAGR (%), 需 ≥6 年数据
    "margins": {
        "gross_margin": [                       # list[dict]
            {"year": int, "value": float},      # (revenue - cost_of_revenue) / revenue × 100
        ],
        "operating_margin": [                   # list[dict]
            {"year": int, "value": float},      # operating_income / revenue × 100
        ],
        "net_margin": [                         # list[dict]
            {"year": int, "value": float},      # net_income / revenue × 100
        ],
    },
}
```

### `health_assessment` 判定逻辑

| 条件 | 评估 |
|------|------|
| ICR < 2 **或** D/E > 3 | `"Weak"` |
| ICR < 5 (且非 Weak) | `"Moderate"` |
| 其他 | `"Strong"` |

### NVDA 示例 (输出)

```json
{
  "health_metrics": {
    "interest_coverage_ratio": 144.03,
    "debt_to_equity": 0.51,
    "roe": 68.28,
    "revenue_cagr_3yr": 31.29,
    "revenue_cagr_5yr": null,
    "margins": {
      "gross_margin": [
        {"year": 2024, "value": 80.93}
      ],
      "operating_margin": [
        {"year": 2024, "value": 58.41}
      ],
      "net_margin": [
        {"year": 2024, "value": 48.85}
      ]
    }
  },
  "health_assessment": "Strong",
  "reasoning_steps": [
    "Interest coverage ratio: 144.03x (Strong)",
    "Debt-to-equity: 0.51 (Conservative)",
    "Net margin: 48.9%",
    "Revenue CAGR (3yr): 31.3%",
    "ROE: 68.3%"
  ]
}
```

## 核心算法

```
1. 利息覆盖率: operating_income / |interest_expense|
   └── > 5 → "Strong"; 2-5 → "Moderate"; < 2 → "Weak"

2. 债务/权益比: total_liabilities / stockholders_equity
   └── < 1 → "Conservative"; < 2 → "Leveraged"; ≥ 2 → "Highly leveraged"

3. 利润率时间序列 (gross_margin, operating_margin, net_margin)
   └── 按年计算: (revenue - cost) / revenue × 100

4. 收入 CAGR: 3年 和 5年复合增长率

5. ROE: net_income / stockholders_equity × 100

6. 综合评估 (与上方判定逻辑表一致):
   ├── ICR < 2 或 D/E > 3 → "Weak"
   ├── ICR < 5 (且非 Weak) → "Moderate"
   └── 其他 → "Strong"
```

## 关键假设

- 利息覆盖率阈值 5x 和债务/权益比阈值 3x 是通用标准，未按行业调整
- 综合评估仅基于 ICR 和 D/E，未考虑利润率趋势

## 失败模式与降级

| 场景 | 处理 |
|------|------|
| financials 为 None | ErrorEvent, return None |
| 利息/负债数据缺失 | 对应指标返回 None |
| 除零 | `_safe_divide` 返回 None |
| 通用异常 | try/except → ErrorEvent |

## 源文件

`backend/agents/nodes/financial_health.py` — 纯计算，无外部 API

## 前端组件

| component_type | 组件 |
|----------------|------|
| `financial_health_card` | `FinancialHealthCard` — 评估徽章 + 指标网格 |
| `revenue_chart` | `RevenueChart` — Recharts 营收柱状图 |
