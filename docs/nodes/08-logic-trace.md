# Node 8: logic_trace

> 图位置: `strategy → logic_trace → END`

## 职责

为每个财务数据点构建到 SEC EDGAR 原始文件的溯源链接，生成最终 Verdict，关闭 SSE 连接。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |
| `dcf_result` | `dict \| None` | ⬜ | → [Node 3 输出](03-dcf-model.md#dcf_result-结构体) |
| `health_assessment` | `str \| None` | ⬜ | → [Node 2 输出](02-financial-health.md#state-更新) |
| `event_sentiment_result` | `dict \| None` | ⬜ | → [Node 5 输出](05-event-sentiment.md#event_sentiment_result-结构体) |
| `event_impact_result` | `dict \| None` | ⬜ | → [Node 6 输出](06-event-impact.md#event_impact_result-结构体) |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.cik` | `int` | ✅ | SEC URL 构建 |
| `financials.entity_name` | `str` | ✅ | Verdict 文本 |
| `financials.ticker` | `str` | ✅ | Verdict 文本 + AnalysisCompleteEvent |
| `financials.<14 个指标字段>` | `list[AnnualMetric]` | ✅ | 溯源数据源 |
| `dcf_result.intrinsic_value_per_share` | `float \| None` | ⬜ | Verdict 内在价值 |
| `health_assessment` | `str` | ⬜ | Verdict 健康评估 |
| `event_sentiment_result.sentiment_label` | `str` | ⬜ | Verdict 情绪 |
| `event_sentiment_result.overall_sentiment` | `float` | ⬜ | Verdict 情绪分数 |
| `event_impact_result.summary` | `str` | ⬜ | Verdict 事件影响 |
| `event_impact_result.recalculated_dcf.intrinsic_value_per_share` | `float` | ⬜ | 优先使用重算价值 |

### 遍历的 14 个指标字段

```
Revenue, Net Income, Operating Income, Total Assets, Total Liabilities,
Stockholders' Equity, Operating Cash Flow, Capital Expenditure, Free Cash Flow,
Interest Expense, Long-Term Debt, Cash & Equivalents, Diluted EPS, Diluted Shares
```

每个字段取最近 **5 年**数据构建溯源记录。

### NVDA 示例 (输入)

```json
{
  "financials": {
    "cik": 1045810,
    "ticker": "NVDA",
    "entity_name": "NVIDIA Corp",
    "revenue": [
      {"calendar_year": 2020, "value": 16675000000, "filing_date": "2020-02-26", "sec_accession": "0001045810-20-000012", "form": "10-K"},
      {"calendar_year": 2021, "value": 26914000000, "filing_date": "2021-02-26", "sec_accession": "0001045810-21-000012", "form": "10-K"},
      {"calendar_year": 2022, "value": 26974000000, "...": "..."},
      {"calendar_year": 2023, "value": 26974000000, "...": "..."},
      {"calendar_year": 2024, "value": 60922000000, "filing_date": "2024-02-28", "sec_accession": "0001045810-24-000012", "form": "10-K"}
    ],
    "free_cash_flow": [{"calendar_year": 2024, "value": 26657000000, "...": "..."}],
    "diluted_eps": [{"calendar_year": 2024, "value": 12.06, "...": "..."}],
    "...": "..."
  },
  "dcf_result": {"intrinsic_value_per_share": 347.99},
  "health_assessment": "Strong",
  "event_sentiment_result": {"sentiment_label": "Bullish", "overall_sentiment": 0.35},
  "event_impact_result": {"summary": "AI demand surge...", "recalculated_dcf": {"intrinsic_value_per_share": 445.94}}
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_map` | `dict[str, list[dict]]` | 14 指标 × 5 年 ≈ 70 个溯源记录 |
| `verdict` | `str \| None` | 最终分析总结文本 |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `source_map` 结构体

> **源码**: `backend/agents/nodes/logic_trace.py` line 96-106

```python
{
    "<Metric Name>": [                          # str → list[dict]
        {
            "metric": str,                     # 指标名称 (e.g. "Revenue")
            "calendar_year": int,              # 日历年
            "value": float,                    # 原始值 ($)
            "form": str,                       # SEC 表单类型 (e.g. "10-K")
            "filed": str,                      # 提交日期
            "accession": str,                  # SEC 登记号
            "url": str,                        # SEC 原始文件 URL
        },
    ],
}
```

> **URL 格式**: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{accession}-index.htm`

### `verdict` 模板

```
"{entity_name} ({ticker}): Financial health is {health_assessment}.
 DCF intrinsic value: ${intrinsic_value}/share.
 Event sentiment: {sentiment_label} (score: {overall_sentiment}).
 Event impact: {event_impact_summary}.
 All {n} data points traced to SEC EDGAR filings."
```

> 内在价值优先使用 `event_impact_result.recalculated_dcf.intrinsic_value_per_share`。
> DCF 不可用时显示 "DCF model could not determine intrinsic value (insufficient data)"。

### NVDA 示例 (输出)

```json
{
  "source_map": {
    "Revenue": [
      {
        "metric": "Revenue",
        "calendar_year": 2024,
        "value": 60922000000,
        "form": "10-K",
        "filed": "2024-02-28",
        "accession": "0001045810-24-000012",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000012/0001045810-24-000012-index.htm"
      },
      {"metric": "Revenue", "calendar_year": 2023, "value": 26974000000, "...": "..."},
      {"metric": "Revenue", "calendar_year": 2022, "value": 26974000000, "...": "..."},
      {"metric": "Revenue", "calendar_year": 2021, "value": 26914000000, "...": "..."},
      {"metric": "Revenue", "calendar_year": 2020, "value": 16675000000, "...": "..."}
    ],
    "Free Cash Flow": [
      {"metric": "Free Cash Flow", "calendar_year": 2024, "value": 26657000000, "...": "..."},
      {"metric": "Free Cash Flow", "calendar_year": 2023, "value": 6908000000, "...": "..."}
    ],
    "Diluted EPS": [
      {"metric": "Diluted EPS", "calendar_year": 2024, "value": 12.06, "...": "..."}
    ]
  },
  "verdict": "NVIDIA Corp (NVDA): Financial health is Strong. DCF intrinsic value: $445.94/share. Event sentiment: Bullish (score: 0.35). Event impact: AI demand surge and Blackwell GPU launch support sustained above-trend growth. All 42 data points traced to SEC EDGAR filings.",
  "reasoning_steps": [
    "Traced 42 data points to SEC filings"
  ]
}
```

## 核心算法

```
1. 遍历 14 个财务指标字段:
   └── 每个取最近 5 年 → 构建:
       {metric, calendar_year, value, form, filed, accession, url}

2. 生成 SEC 原始文件 URL:
   └── https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{accession}-index.htm

3. 构建 Verdict (聚合所有节点结果):
   "{entity} ({ticker}): Health {assessment}.
    DCF ${value}/share. Sentiment {label} ({score}).
    {event_impact_summary}.
    {n} data points traced to SEC EDGAR."

4. 发射 AnalysisCompleteEvent → 前端关闭 SSE
```

## 关键假设

- 只追踪最近 5 年数据，不包含全部历史
- Verdict 格式是固定模板，未使用 LLM 生成

## 失败模式与降级

| 场景 | 处理 |
|------|------|
| financials 为 None | ErrorEvent, return {source_map: None, verdict: None} |
| 通用异常 | ErrorEvent + AnalysisCompleteEvent (确保 SSE 关闭) |
| 部分指标缺失 | 跳过该指标 |

## 源文件

`backend/agents/nodes/logic_trace.py` — 纯计算 + URL 构建，无外部 API

## 前端组件

| component_type | 组件 |
|----------------|------|
| `source_table` | `SourceTable` — 溯源表 (指标/值/年份/SEC 链接) |
