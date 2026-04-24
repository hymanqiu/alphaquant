# Node 1: fetch_sec_data

> 图位置: `START → fetch_sec_data → [条件分支]`

## 职责

从 SEC EDGAR 获取原始 XBRL 数据并归一化为统一的 `CompanyFinancials` 对象，作为整个分析管线的起点。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `ticker` | `str` | ✅ | 用户输入的股票代码 |

### NVDA 示例 (输入)

```json
{ "ticker": "NVDA" }
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `financials` | `CompanyFinancials \| None` | 归一化后的财务数据 (16 个字段 × 多年) |
| `fetch_errors` | `list[str]` | 获取失败的错误信息 |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

条件分支: `_should_continue(state)` — `financials` 不为 None → continue；否则 → END

### `CompanyFinancials` 结构体

> **定义**: `backend/models/financial.py`

```python
class CompanyFinancials(BaseModel):
    cik: int                           # SEC CIK 编号
    ticker: str                        # 股票代码
    entity_name: str                   # 公司全称
    # --- 16 个财务指标 (15 XBRL + 1 计算 FCF, 均为 list[AnnualMetric]) ---
    revenue: list[AnnualMetric] = []
    net_income: list[AnnualMetric] = []
    operating_income: list[AnnualMetric] = []
    total_assets: list[AnnualMetric] = []
    total_liabilities: list[AnnualMetric] = []
    stockholders_equity: list[AnnualMetric] = []
    operating_cash_flow: list[AnnualMetric] = []
    capital_expenditure: list[AnnualMetric] = []
    free_cash_flow: list[AnnualMetric] = []          # = OCF - |CapEx|
    interest_expense: list[AnnualMetric] = []
    long_term_debt: list[AnnualMetric] = []
    cash_and_equivalents: list[AnnualMetric] = []
    diluted_eps: list[AnnualMetric] = []
    diluted_shares: list[AnnualMetric] = []
    cost_of_revenue: list[AnnualMetric] = []
    depreciation_and_amortization: list[AnnualMetric] = []
```

### `AnnualMetric` 结构体

> **定义**: `backend/models/financial.py`

```python
class AnnualMetric(BaseModel):
    calendar_year: int        # 日历年
    value: float              # 值 (美元)
    fiscal_year: int          # 财年
    filing_date: str          # 提交日期
    sec_accession: str        # SEC 登记号
    form: str                 # 表单类型 (10-K)
```

### NVDA 示例 (输出)

```json
{
  "financials": {
    "cik": 1045810,
    "ticker": "NVDA",
    "entity_name": "NVIDIA Corp",
    "revenue": [
      {"calendar_year": 2021, "value": 26914000000, "fiscal_year": 2021,
       "filing_date": "2021-02-26", "sec_accession": "0001045810-21-000012", "form": "10-K"},
      {"calendar_year": 2022, "value": 26974000000, "fiscal_year": 2022, "...": "..."},
      {"calendar_year": 2023, "value": 26974000000, "fiscal_year": 2023, "...": "..."},
      {"calendar_year": 2024, "value": 60922000000, "fiscal_year": 2024, "...": "..."}
    ],
    "net_income": [
      {"calendar_year": 2024, "value": 29760000000, "...": "..."}
    ],
    "free_cash_flow": [
      {"calendar_year": 2024, "value": 26657000000, "...": "..."}
    ],
    "diluted_eps": [
      {"calendar_year": 2024, "value": 12.06, "...": "..."}
    ],
    "diluted_shares": [
      {"calendar_year": 2024, "value": 2487000000, "...": "..."}
    ],
    "long_term_debt": [
      {"calendar_year": 2024, "value": 8461000000, "...": "..."}
    ],
    "stockholders_equity": [
      {"calendar_year": 2024, "value": 43585000000, "...": "..."}
    ],
    "interest_expense": [
      {"calendar_year": 2024, "value": 247000000, "...": "..."}
    ],
    "cash_and_equivalents": [
      {"calendar_year": 2024, "value": 25896000000, "...": "..."}
    ],
    "operating_income": [],
    "total_assets": [],
    "total_liabilities": [],
    "operating_cash_flow": [],
    "capital_expenditure": [],
    "cost_of_revenue": [],
    "depreciation_and_amortization": []
  },
  "fetch_errors": [],
  "reasoning_steps": [
    "Fetched SEC data for NVIDIA Corp",
    "Available data series: 5"
  ]
}
```

## 核心算法

```
1. ticker_resolver.resolve(ticker) → (cik, entity_name)
   └── 内存缓存，启动时从 sec.gov 加载

2. sec_client.get_company_facts(cik) → SECCompanyFacts (原始 XBRL)
   └── 速率限制: 10 req/s (100ms 间隔)

3. _normalize(facts, ticker) → CompanyFinancials (归一化)
   ├── 遍历 TAG_MAP (15 个 XBRL 字段 × 1-5 个候选标签)
   ├── 对每个字段: 尝试所有候选, 选 latest_year 最大的
   ├── Frame 去重: CYxxxx (duration) ✓, CYxxxxQ4I (instant) ✓, CYxxxxQx (季度) ✗
   ├── 计算 FCF = OCF - |CapEx| (按日历年匹配)
   └── 返回 16 个 list[AnnualMetric]

4. 发射 SSE 事件: AgentThinking × 2, Component("metric_table"), StepComplete
```

## 关键假设

- **XBRL 标签回退策略**: 多候选标签中选 latest_year 最大的 → [ADR 001](../decisions/001-xbrl-tag-fallback.md)
- **Frame 去重**: 只保留有 frame 字段的条目，过滤季度数据
- **数据完整性**: 假设 SEC 10-K 年报数据足够可靠作为估值基础

## 失败模式与降级

| 场景 | 处理 | 前端表现 |
|------|------|----------|
| Ticker 不存在 | `TickerNotFoundError` → `ErrorEvent(recoverable=False)` | 红色错误条 |
| SEC API 超时/5xx | `ErrorEvent(recoverable=False)` | 红色错误条 |
| SEC API 429 | `_rate_limit()` 自动等待 | 用户无感 |
| XBRL 标签不存在 | 字段返回空列表 `[]` | 指标显示 "N/A" |
| 通用异常 | `ErrorEvent` + `AnalysisCompleteEvent` | 错误条 + 流结束 |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/value_analyst.py` | `fetch_sec_data_node()` 节点入口 |
| `backend/services/sec_agent.py` | XBRL 归一化核心逻辑 |
| `backend/services/ticker_resolver.py` | Ticker → CIK 映射 |
| `backend/services/sec_client.py` | EDGAR HTTP 客户端 |
| `backend/models/financial.py` | `CompanyFinancials`, `AnnualMetric` 数据模型 |

## 前端组件

| component_type | 组件 |
|----------------|------|
| `metric_table` | `MetricTable` — 关键指标表 (Revenue, Net Income, FCF, EPS) |
