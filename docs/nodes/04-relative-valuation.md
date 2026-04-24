# Node 4: relative_valuation

> 图位置: `dynamic_dcf → relative_valuation → event_sentiment`

## 职责

结合实时市场价格计算当前估值乘数 (P/E, P/B, P/S 等)、历史百分位排名和同业对比偏差，提供市场定价参考。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |

### 子字段访问

节点实际从 `financials` 访问以下子字段 (`_run_relative_valuation` + `compute_current_multiples`):

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.ticker` | `str` | ✅ | API 调用参数 |
| `financials.entity_name` | `str` | ✅ | UI 显示 |
| `financials.diluted_shares` | `list[AnnualMetric]` | ✅ | 市值计算 |
| `financials.diluted_eps` | `list[AnnualMetric]` | ⬜ | P/E, PEG |
| `financials.revenue` | `list[AnnualMetric]` | ⬜ | P/S, EV/Revenue |
| `financials.net_income` | `list[AnnualMetric]` | ⬜ | P/FFO |
| `financials.operating_income` | `list[AnnualMetric]` | ⬜ | EV/EBIT |
| `financials.free_cash_flow` | `list[AnnualMetric]` | ⬜ | EV/FCF |
| `financials.stockholders_equity` | `list[AnnualMetric]` | ⬜ | P/B |
| `financials.long_term_debt` | `list[AnnualMetric]` | ⬜ | EV |
| `financials.cash_and_equivalents` | `list[AnnualMetric]` | ⬜ | EV |
| `financials.depreciation_and_amortization` | `list[AnnualMetric]` | ⬜ | FFO |

### NVDA 示例 (输入子字段)

```json
{
  "ticker": "NVDA",
  "entity_name": "NVIDIA Corp",
  "diluted_shares":   [{"calendar_year": 2024, "value": 2487000000}],
  "diluted_eps":      [{"calendar_year": 2024, "value": 12.06}],
  "revenue":          [{"calendar_year": 2024, "value": 60922000000}],
  "net_income":       [{"calendar_year": 2024, "value": 29760000000}],
  "operating_income": [{"calendar_year": 2024, "value": 35577000000}],
  "free_cash_flow":   [{"calendar_year": 2024, "value": 26657000000}],
  "stockholders_equity": [{"calendar_year": 2024, "value": 43585000000}],
  "long_term_debt":   [{"calendar_year": 2024, "value": 8461000000}],
  "cash_and_equivalents": [{"calendar_year": 2024, "value": 25896000000}]
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `relative_valuation_result` | `dict \| None` | 相对估值结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `relative_valuation_result` 结构体

> **源码**: `backend/agents/nodes/relative_valuation.py` line 251-266

```python
{
    # --- 降级路径 (无价格时): price_available=False, peer_data_available=False ---
    "price_available": bool,                          # 价格是否可用
    "current_price": float | None,                   # 实时价格 ($)
    "annual_prices": dict[int, float] | None,         # {year: closing_price}
    "market_cap": float | None,                       # 市值 ($)
    "enterprise_value": float | None,                 # EV = mkt_cap + debt - cash ($)
    "current_multiples": {                            # 当前乘数 (均为 float | None)
        "pe": float | None,                           # price / EPS
        "pb": float | None,                           # mkt_cap / equity
        "ps": float | None,                           # mkt_cap / revenue
        "ev_to_revenue": float | None,                # EV / revenue
        "ev_to_ebit": float | None,                   # EV / operating_income
        "ev_to_fcf": float | None,                    # EV / FCF
        "p_ffo": float | None,                        # mkt_cap / (NI + D&A)
        "dividend_yield": float | None,               # (%)
        "peg": float | None,                          # P/E / earnings_growth
    },
    "historical_stats": {                             # dict[str, dict]
        "<multiple_name>": {
            "series": [{"year": int, "value": float}],
            "median": float | None,
            "average": float | None,
            "count": int,
        },
    },
    "percentiles": {                                  # 当前值在历史中的百分位
        "pe": float | None,                           # 0-100
        "pb": float | None,
        "ps": float | None,
        "ev_to_revenue": float | None,
        "ev_to_ebit": float | None,
        "p_ffo": float | None,
    },
    "peer_comparison": {                              # 同业对比 (可能为 None)
        "peer_data_available": bool,
        "peers": list[str],                           # 同业代码列表
        "peer_medians": {"peRatio": float, ...},      # FMP key → median
        "peer_table": [{"ticker": str, ...}],         # 同业乘数表
        "deltas": {                                   # 公司值 vs 同业中位数偏差 (%)
            "pe": float | None,                       # (company - peer_med) / peer_med × 100
            "pb": float | None,
            "ps": float | None,
            "ev_to_revenue": float | None,
        },
    } | None,
    "sector": str | None,                             # 行业
    "industry": str | None,                           # 子行业
    "recommended_multiples": list[str],               # 推荐关注的乘数
    "industry_explanation": str,                      # 行业说明
    "dividend_yield": float | None,                   # 股息率 (%)
}
```

> **价格获取**: 优先 `FMP /stable/quote`，回退 `/stable/profile.price`。
> **无 FMP Key**: `price_available=false`, `current_multiples={}`, 跳过所有价格计算。

### NVDA 示例 (输出)

```json
{
  "relative_valuation_result": {
    "price_available": true,
    "current_price": 880.00,
    "annual_prices": {2021: 294.0, 2022: 146.0, 2023: 495.0, 2024: 880.0},
    "market_cap": 2189000000000,
    "enterprise_value": 2171000000000,
    "current_multiples": {
      "pe": 72.97,
      "pb": 50.22,
      "ps": 35.93,
      "ev_to_revenue": 35.63,
      "ev_to_ebit": 61.03,
      "ev_to_fcf": 81.45,
      "p_ffo": 68.57,
      "dividend_yield": 0.02,
      "peg": 2.34
    },
    "historical_stats": {
      "pe": {
        "series": [{"year": 2021, "value": 87.5}, {"year": 2022, "value": 45.2}, "...": "..."],
        "median": 65.0,
        "average": 62.3,
        "count": 4
      }
    },
    "percentiles": {"pe": 85.0, "pb": 90.0, "ps": 88.0},
    "peer_comparison": {
      "peer_data_available": true,
      "peers": ["AMD", "INTC", "QCOM", "AVGO"],
      "peer_medians": {"peRatio": 28.5, "pbRatio": 6.2, "priceToSalesRatio": 8.1},
      "peer_table": [{"ticker": "AMD", "peRatio": 45.2, "...": "..."}],
      "deltas": {"pe": 155.9, "pb": 709.0, "ps": 343.2, "ev_to_revenue": 339.9}
    },
    "sector": "Technology",
    "industry": "Semiconductors",
    "recommended_multiples": ["pe", "ps", "ev_to_revenue"],
    "industry_explanation": "Semiconductor companies are typically valued on P/S and EV/Revenue...",
    "dividend_yield": 0.02
  },
  "reasoning_steps": [
    "Industry: Technology / Semiconductors — recommended multiples: pe, ps, ev_to_revenue",
    "Market cap: $2,189,000,000,000",
    "Enterprise value: $2,171,000,000,000",
    "P/E at 85th historical percentile",
    "vs peer median — pe: +156%, pb: +709%, ps: +343%, ev_to_revenue: +340%"
  ]
}
```

## 核心算法

```
1. 获取实时价格: FMP /stable/quote + /stable/profile 并行
   └── 失败 → price_available=false, 优雅降级

2. 计算当前乘数 (relative_valuation_math.py):
   P/E, P/B, P/S, EV/Revenue, EV/EBIT, EV/FCF, PEG, P/FFO, Dividend Yield
   └── 所有除法使用 safe_divide

3. 历史百分位 (10 年):
   ├── get_annual_closing_prices → 每年收盘价
   ├── 交叉匹配: 年终股价 × SEC 数据 → 每年各乘数
   └── percentile_rank(current, series) → 百分位

4. 同业对比:
   ├── get_peers → 同业列表
   ├── get_batch_peer_metrics → 并发获取 TTM 乘数
   ├── 计算同行中位数
   └── delta% = (公司值 - 中位数) / |中位数| × 100 (源码使用 abs())

5. 行业映射: industry_mapping.py → 推荐关注哪些乘数
```

## 关键假设

- **FMP /stable/ API 作为市场数据源** → [ADR 005](../decisions/005-fmp-stable-api.md)
- 历史百分位基于年终收盘价 × SEC 原始 EPS（不使用调整后数据）
- 同业列表来自 FMP，非 GICS 行业分类
- 所有 API 调用失败时优雅降级，不阻塞主流程

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| 无 FMP API Key | `price_available=false`, 跳过所有价格计算 |
| FMP 超时/错误 | `get_current_price()` 返回 None → 同上 |
| 有 Key 但无同业 | `peer_data_available=false`, 前端隐藏同业表 |
| 完整数据 | 全分析: 当前乘数 + 历史百分位 + 同业偏差 |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/relative_valuation.py` | 节点入口 + 数据获取编排 |
| `backend/agents/nodes/relative_valuation_math.py` | 纯计算 (无 I/O) |
| `backend/agents/nodes/industry_mapping.py` | 行业分类 + 推荐乘数 |
| `backend/services/market_data.py` | FMP HTTP 客户端 |

## 配置依赖

| 环境变量 | 必需 | 说明 |
|----------|------|------|
| `AQ_FMP_API_KEY` | 可选 | 未设置时节点降级 (不报错) |

## 前端组件

| component_type | 组件 |
|----------------|------|
| `relative_valuation_card` | `RelativeValuationCard` — 乘数网格 + 历史百分位条形图 + 同业对比表 |
