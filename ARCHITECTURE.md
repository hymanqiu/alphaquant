# AlphaQuant - System Architecture & Workflow

## 1. System Overview

AlphaQuant is a white-box AI investment research system. It fetches raw SEC EDGAR filings, runs multi-step value analysis through a LangGraph state machine, and streams the reasoning process and results as Generative UI components to a React frontend in real-time via Server-Sent Events (SSE).

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js 16)                       │
│                                                                     │
│  ┌──────────────┐     ┌─────────────┐     ┌──────────────────────┐ │
│  │  Home Page    │────>│  useSSE     │────>│  AnalysisLayout      │ │
│  │  (Ticker Input)     │  (EventSource)    │  ┌────────┐┌───────┐│ │
│  └──────────────┘     └──────┬──────┘     │  │Terminal ││Visual-││ │
│                              │             │  │(思考链) ││izer   ││ │
│                              │             │  └────────┘└───┬───┘│ │
│                              │             └────────────────┼────┘ │
│                              │                              │      │
│                    SSE Stream│              Component Registry      │
│                    (实时推送) │              (lazy load 8 组件)     │
└──────────────────────────────┼──────────────────────────────┼──────┘
                               │                              │
                        GET /api/analyze/{ticker}    POST /api/recalculate-dcf
                               │                              │
┌──────────────────────────────┼──────────────────────────────┼──────┐
│                         Backend (FastAPI)                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  LangGraph StateGraph                        │   │
│  │                                                              │   │
│  │  START ──> fetch_sec_data ──┬──> financial_health_scan       │   │
│  │                             │         │                      │   │
│  │                          [error]      v                      │   │
│  │                             │    dynamic_dcf                 │   │
│  │                             v         │                      │   │
│  │                            END        v                      │   │
│  │                              logic_trace ──> END             │   │
│  └──────────────────────┬──────────────────────────────────────┘   │
│                         │                                           │
│                    StreamWriter                                     │
│                    (每个节点实时发射事件)                             │
│                         │                                           │
│  ┌──────────────────────v──────────────────────────────────────┐   │
│  │              SEC Data Pipeline                               │   │
│  │  TickerResolver ──> SECClient ──> SECDataService             │   │
│  │  (ticker→CIK)      (EDGAR API)    (XBRL归一化)              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               v
                    ┌─────────────────────┐
                    │   SEC EDGAR API      │
                    │   data.sec.gov       │
                    │   (XBRL/JSON)        │
                    └─────────────────────┘
```

---

## 2. Directory Structure

```
alpha/
├── backend/
│   ├── pyproject.toml                          # Python 依赖定义
│   ├── backend/
│   │   ├── main.py                             # FastAPI 入口 + lifespan 管理
│   │   ├── config.py                           # pydantic-settings 配置
│   │   ├── models/
│   │   │   ├── sec.py                          # SEC EDGAR 原始响应模型
│   │   │   ├── financial.py                    # 归一化后的财务指标模型
│   │   │   ├── agent_state.py                  # LangGraph TypedDict 状态
│   │   │   └── events.py                       # SSE 事件模型 (Generative UI 协议)
│   │   ├── services/
│   │   │   ├── ticker_resolver.py              # Ticker → CIK 映射
│   │   │   ├── sec_client.py                   # EDGAR HTTP 客户端 (httpx)
│   │   │   └── sec_agent.py                    # XBRL 归一化层 (核心领域逻辑)
│   │   ├── agents/
│   │   │   ├── value_analyst.py                # LangGraph StateGraph 编排
│   │   │   └── nodes/
│   │   │       ├── financial_health.py         # 节点1: 财务健康扫描
│   │   │       ├── dcf_model.py                # 节点2: 动态 DCF 建模
│   │   │       └── logic_trace.py              # 节点3: 数据溯源
│   │   └── api/
│   │       ├── routes.py                       # SSE + 重算端点
│   │       └── dependencies.py                 # 内存缓存 (DCF 重算用)
│   └── tests/
│
└── frontend/
    └── src/
        ├── app/
        │   ├── layout.tsx                      # 根布局
        │   ├── page.tsx                        # 首页 (Ticker 输入)
        │   └── analyze/[ticker]/page.tsx       # 分析页 (动态路由)
        ├── hooks/
        │   ├── use-sse.ts                      # 底层 EventSource 封装
        │   └── use-analysis-stream.ts          # 高层分析流 Hook
        ├── components/
        │   ├── agent-terminal.tsx              # 打字机效果终端
        │   ├── visualizer.tsx                  # 动态组件挂载器
        │   ├── component-registry.ts           # 类型 → React 组件映射
        │   ├── layout/
        │   │   └── analysis-layout.tsx         # 双栏布局 + 重算逻辑
        │   └── analysis/
        │       ├── metric-table.tsx            # 关键指标表
        │       ├── revenue-chart.tsx           # 营收柱状图
        │       ├── fcf-chart.tsx               # FCF 历史+预测图
        │       ├── financial-health-card.tsx    # 财务健康卡片
        │       ├── dcf-result-card.tsx          # DCF 估值结果
        │       ├── valuation-gauge.tsx          # 估值仪表
        │       ├── assumption-slider.tsx        # 假设参数滑块
        │       └── source-table.tsx             # SEC 数据溯源表
        └── lib/
            ├── types.ts                        # TypeScript 类型定义
            ├── constants.ts                    # API 地址常量
            └── utils.ts                        # 工具函数
```

---

## 3. Complete Request Lifecycle (以 NVDA 为例)

### Phase 0: Application Startup

```
main.py: lifespan()
    │
    ├── ticker_resolver.load()
    │   └── GET https://www.sec.gov/files/company_tickers.json
    │       └── 解析约 10,000+ 公司映射: {"NVDA": (1045810, "NVIDIA CORP"), ...}
    │       └── 存入内存字典 _cache
    │
    └── FastAPI app ready on :8000
        ├── CORS 允许 localhost:3000
        └── 路由注册: GET /api/analyze/{ticker}, POST /api/recalculate-dcf
```

### Phase 1: User Input (Frontend)

```
用户访问 http://localhost:3000
    │
    ├── app/page.tsx 渲染
    │   ├── 输入框: "Enter ticker symbol"
    │   └── 快捷按钮: [NVDA] [AAPL] [MSFT] [GOOGL] [AMZN]
    │
    ├── 用户输入 "NVDA" + Enter (或点击 NVDA 按钮)
    │   └── router.push('/analyze/NVDA')
    │
    └── app/analyze/[ticker]/page.tsx 渲染
        ├── const { ticker } = use(params)  // Next.js 16: params 是 Promise
        └── <AnalysisLayout ticker="NVDA" />
```

### Phase 2: SSE Connection (Frontend → Backend)

```
AnalysisLayout 挂载
    │
    ├── useAnalysisStream("NVDA")
    │   └── useSSE({ url: "http://localhost:8000/api/analyze/NVDA" })
    │       └── new EventSource(url)
    │           ├── 注册监听: agent_thinking, component, step_complete,
    │           │              analysis_complete, error
    │           └── status: "connecting" → "connected"
    │
    └── 渲染初始 UI
        ├── AgentTerminal: "Initializing analysis..." (动画)
        └── Visualizer: 空 (等待组件)
```

### Phase 3: Backend Graph Execution

当 EventSource 连接到 `GET /api/analyze/NVDA`，FastAPI 执行以下流程：

```
routes.py: analyze_ticker("NVDA")
    │
    ├── graph = build_value_analyst_graph().compile()
    │   └── StateGraph(AnalysisState) 构建:
    │       START ──> fetch_sec_data ──[条件]──> financial_health_scan
    │                                    │              │
    │                                 [error→END]       v
    │                                              dynamic_dcf
    │                                                   │
    │                                                   v
    │                                              logic_trace ──> END
    │
    ├── initial_state = {
    │       ticker: "NVDA",
    │       financials: None,    # 待填充
    │       fetch_errors: [],
    │       health_metrics: None,
    │       health_assessment: None,
    │       dcf_result: None,
    │       source_map: None,
    │       reasoning_steps: [],  # Annotated[list, add] 追加模式
    │       verdict: None,
    │   }
    │
    └── graph.astream(initial_state, stream_mode=["custom", "values"])
        │
        │  stream_mode 说明:
        │  - "custom": 接收节点通过 StreamWriter 发射的自定义事件
        │  - "values": 接收节点返回的状态更新 (用于缓存 financials)
        │
        └── 进入节点执行循环 ──────────────────────────────────┐
                                                               │
```

#### Node 1: `fetch_sec_data` (SEC 数据获取)

```
fetch_sec_data_node(state, writer)
    │
    ├── writer(AgentThinkingEvent("Fetching SEC EDGAR filing data for NVDA..."))
    │   └── → SSE event: agent_thinking
    │       └── 前端 AgentTerminal 显示打字机动画
    │
    ├── sec_data_service.get_financials("NVDA")
    │   │
    │   ├── ticker_resolver.resolve("NVDA")
    │   │   └── 查询内存缓存 → (cik=1045810, name="NVIDIA CORP")
    │   │
    │   ├── sec_client.get_company_facts(1045810)
    │   │   ├── _rate_limit(): 确保间隔 ≥ 100ms (10 req/s)
    │   │   ├── GET https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json
    │   │   │   └── Headers: User-Agent: "AlphaQuant Research contact@alphaquant.dev"
    │   │   └── SECCompanyFacts.model_validate(resp.json())
    │   │       └── 解析结构: {cik, entityName, facts: {us-gaap: {tag: SECFact}}}
    │   │
    │   └── _normalize(company_facts, "NVDA")
    │       │
    │       │  ┌─── 对每个财务字段执行 ───────────────────────────────────┐
    │       │  │                                                          │
    │       │  │  TAG_MAP 定义了 15 个字段的 XBRL 标签回退链:            │
    │       │  │                                                          │
    │       │  │  "revenue" → 尝试:                                      │
    │       │  │    1. Revenues                ← NVDA 使用此标签          │
    │       │  │    2. RevenueFromContract...ExcludingAssessedTax         │
    │       │  │    3. RevenueFromContract...IncludingAssessedTax         │
    │       │  │    4. SalesRevenueNet                                    │
    │       │  │    5. SalesRevenueGoodsNet                               │
    │       │  │                                                          │
    │       │  │  "capital_expenditure" → 尝试:                          │
    │       │  │    1. PaymentsToAcquirePropertyPlantAndEquipment         │
    │       │  │    2. PaymentsToAcquireProductiveAssets ← NVDA 近年用此  │
    │       │  │                                                          │
    │       │  │  选择策略: 所有候选标签都尝试,                          │
    │       │  │  选择 latest_year 最大的那个 (不是第一个匹配)           │
    │       │  └──────────────────────────────────────────────────────────┘
    │       │
    │       │  ┌─── _extract_for_tag 提取逻辑 ───────────────────────────┐
    │       │  │                                                          │
    │       │  │  1. 根据 UNIT_MAP 选择单位:                             │
    │       │  │     - 大部分字段: USD                                    │
    │       │  │     - diluted_eps: USD/shares                            │
    │       │  │     - diluted_shares: shares                             │
    │       │  │                                                          │
    │       │  │  2. 过滤条件:                                           │
    │       │  │     - form == "10-K" (年报) AND fp == "FY" (全年)        │
    │       │  │     - frame != None (只要有 frame 标签的规范值)          │
    │       │  │                                                          │
    │       │  │  3. Frame 去重逻辑 (核心):                              │
    │       │  │     - "CY2024"   → 收入/利润等 duration 指标 ✓ 保留      │
    │       │  │     - "CY2024Q4I"→ 资产/负债等 instant 指标 ✓ 保留       │
    │       │  │     - "CY2024Q1" → 季度数据 ✗ 跳过 (正则 Q\d$ 过滤)    │
    │       │  │                                                          │
    │       │  │  4. 同一日历年有多个条目时, 取 filed 日期最新的          │
    │       │  │                                                          │
    │       │  │  5. 按 calendar_year 排序返回                            │
    │       │  └──────────────────────────────────────────────────────────┘
    │       │
    │       ├── 计算 FCF = OCF - |CapEx| (按日历年匹配)
    │       │
    │       └── 返回 CompanyFinancials:
    │           ├── revenue: 18 年 (2007-2025), 最新 $215.9B
    │           ├── net_income: 19 年, 最新 $120.1B
    │           ├── operating_cash_flow: 19 年, 最新 $102.7B
    │           ├── capital_expenditure: 5 年, 最新 $6.0B
    │           ├── free_cash_flow: 5 年, 最新 $96.7B (102.7 - 6.0)
    │           ├── total_assets: 18 年, 最新 $206.8B
    │           ├── stockholders_equity: 20 年, 最新 $157.3B
    │           ├── long_term_debt: 14 年, 最新 $8.5B
    │           ├── diluted_eps: 最新 $4.90
    │           └── diluted_shares: 最新 24.5B 股
    │
    ├── writer(AgentThinkingEvent("Successfully loaded data for NVIDIA CORP"))
    │   └── → SSE event: agent_thinking
    │
    ├── writer(ComponentEvent("metric_table", {title, metrics: [...]}))
    │   └── → SSE event: component
    │       └── 前端 Visualizer 挂载 MetricTable 组件
    │           显示: Revenue $215.9B, Net Income $120.1B, FCF $96.7B, EPS $4.90
    │
    ├── writer(StepCompleteEvent("Loaded 5 financial data series"))
    │   └── → SSE event: step_complete
    │
    └── return {
            financials: CompanyFinancials(...),  # 写入共享状态
            fetch_errors: [],
            reasoning_steps: ["Fetched SEC data...", "Available: 5"],
        }
        │
        └── _should_continue(state) → state["financials"] is not None → "continue"
            └── 进入下一节点
```

#### Node 2: `financial_health_scan` (财务健康扫描)

```
financial_health_node(state, writer)
    │
    ├── 从 state["financials"] 读取已归一化的数据
    │
    ├── 计算利息覆盖率:
    │   ├── operating_income[-1] = $130.4B
    │   ├── interest_expense[-1] = $257M
    │   └── ICR = 130,387 / 257 = 507.34x → "Strong"
    │
    ├── 计算债务/权益比:
    │   ├── total_liabilities[-1] = $49.5B
    │   ├── stockholders_equity[-1] = $157.3B
    │   └── D/E = 49.5 / 157.3 = 0.31x → "Conservative"
    │
    ├── 计算利润率 (按年时间序列):
    │   ├── gross_margin: (revenue - cost_of_revenue) / revenue × 100
    │   │   └── 最新: 71.1%
    │   ├── operating_margin: operating_income / revenue × 100
    │   │   └── 最新: 60.4%
    │   └── net_margin: net_income / revenue × 100
    │       └── 最新: 55.6%
    │
    ├── 计算收入 CAGR:
    │   ├── 3 年: (215.9B / 27.0B)^(1/3) - 1 = 100.1%
    │   └── 5 年: (215.9B / 6.9B)^(1/5) - 1 = 66.9%
    │
    ├── 计算 ROE:
    │   └── net_income / equity = 120.1B / 157.3B = 76.3%
    │
    ├── 综合评估: ICR > 5 且 D/E < 3 → "Strong"
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 4 (每个指标)
    │   ├── ComponentEvent("financial_health_card", {assessment: "Strong", ...})
    │   │   └── 前端挂载 FinancialHealthCard: 绿色"Strong"徽章 + 指标网格
    │   ├── ComponentEvent("revenue_chart", {data: [{year, revenue} × 18]})
    │   │   └── 前端挂载 RevenueChart: Recharts BarChart 18年营收
    │   └── StepCompleteEvent
    │
    └── return {health_metrics, health_assessment: "Strong", reasoning_steps}
```

#### Node 3: `dynamic_dcf` (DCF 估值建模)

```
dcf_node(state, writer)
    │
    ├── 从 state["financials"].free_cash_flow 读取历史 FCF
    │   └── [2021: $8.1B, 2022: $3.8B, 2023: $27.0B, 2024: $60.9B, 2025: $96.7B]
    │
    ├── 估算增长率:
    │   ├── _fcf_cagr(fcf, 3) = (96.7/27.0)^(1/3) - 1 = 53.0% (3年)
    │   ├── _fcf_cagr(fcf, 5) → 无法计算 (数据不足)
    │   ├── raw_growth = 53.0% (仅有 3 年)
    │   └── 封顶: min(53.0%, 30%) = 30.0%
    │
    ├── 估算 WACC:
    │   ├── _estimate_wacc(debt=8.5B, equity=157.3B, interest=257M)
    │   ├── cost_of_equity = 4.5% + 1.2 × 5.5% = 11.1%
    │   ├── cost_of_debt = 257M / 8.5B = 3.0%
    │   ├── WACC = (157.3/165.8)×11.1% + (8.5/165.8)×3.0%×(1-0.21)
    │   └── = 10.66%
    │
    ├── terminal_growth = 3.0% (固定假设)
    │
    ├── compute_dcf(latest_fcf=96.7B, growth=30%, terminal=3%, discount=10.66%)
    │   │
    │   │  ┌─── 2 阶段 DCF 模型 ──────────────────────────────────────┐
    │   │  │                                                            │
    │   │  │  Phase 1 (Year 1-5): 恒定高增长 30.0%                    │
    │   │  │    Y1: 96.7B × 1.30 = $125.7B                            │
    │   │  │    Y2: 125.7B × 1.30 = $163.4B                           │
    │   │  │    Y3: 163.4B × 1.30 = $212.4B                           │
    │   │  │    Y4: 212.4B × 1.30 = $276.1B                           │
    │   │  │    Y5: 276.1B × 1.30 = $359.0B                           │
    │   │  │                                                            │
    │   │  │  Phase 2 (Year 6-10): 线性衰减 30% → 3%                  │
    │   │  │    Y6:  增长率 = 30% + (3%-30%) × 1/5 = 24.6%            │
    │   │  │    Y7:  增长率 = 30% + (3%-30%) × 2/5 = 19.2%            │
    │   │  │    Y8:  增长率 = 30% + (3%-30%) × 3/5 = 13.8%            │
    │   │  │    Y9:  增长率 = 30% + (3%-30%) × 4/5 = 8.4%             │
    │   │  │    Y10: 增长率 = 30% + (3%-30%) × 5/5 = 3.0%             │
    │   │  │                                                            │
    │   │  │  Terminal Value:                                           │
    │   │  │    TV = Y10_FCF × (1+3%) / (10.66% - 3%) = $9.1T         │
    │   │  │    PV(TV) = $9.1T / (1.1066)^10 = $3.3T                  │
    │   │  │                                                            │
    │   │  │  Enterprise Value = PV(FCF_sum) + PV(TV) = $5.4T          │
    │   │  │  Intrinsic Value/Share = $5.4T / 24.5B shares = $220.36   │
    │   │  └────────────────────────────────────────────────────────────┘
    │   │
    │   └── 返回 DCFResult
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 4
    │   ├── ComponentEvent("fcf_chart", {data: historical(5) + projected(10)})
    │   │   └── 前端: 深色柱 = 历史, 浅色柱 = 预测
    │   ├── ComponentEvent("dcf_result_card", {intrinsic: $220.36, EV: $5.4T, ...})
    │   ├── ComponentEvent("valuation_gauge", {intrinsic_value: 220.36})
    │   ├── ComponentEvent("assumption_slider", {growth: 30, discount: 10.66, terminal: 3})
    │   │   └── 前端: 三个滑块 + "Recalculate DCF" 按钮
    │   └── StepCompleteEvent
    │
    └── return {dcf_result: {...}, reasoning_steps}
```

#### Node 4: `logic_trace` (数据溯源)

```
logic_trace_node(state, writer)
    │
    ├── 遍历 14 个财务指标字段, 取每个字段最近 5 年的数据
    │   └── 对每条记录构建:
    │       {
    │           metric: "Revenue",
    │           calendar_year: 2025,
    │           value: 215938000000,
    │           form: "10-K",
    │           filed: "2026-02-25",
    │           accession: "0001045810-26-000021",
    │           url: "https://www.sec.gov/Archives/edgar/data/1045810/..."
    │       }
    │
    ├── 共计 70 个数据点, 覆盖 14 个指标
    │
    ├── 构建最终 verdict:
    │   └── "NVIDIA CORP (NVDA): Financial health is Strong.
    │        DCF intrinsic value: $220.36/share.
    │        All 70 data points traced to SEC EDGAR filings."
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 2
    │   ├── ComponentEvent("source_table", {sources: [70 entries]})
    │   │   └── 前端: 每行显示指标名/值/年份, 可点击跳转 SEC 原始文件
    │   ├── StepCompleteEvent
    │   └── AnalysisCompleteEvent(verdict, ticker)
    │       └── 前端: useSSE 检测到此事件 → status = "complete" → 关闭 EventSource
    │
    └── return {source_map, verdict, reasoning_steps}
```

### Phase 4: Frontend Rendering (全程实时)

```
SSE 事件流时序 (共约 20 个事件):
    │
    │  ┌─ AgentTerminal (左栏 2/5) ──────────┐  ┌─ Visualizer (右栏 3/5) ────────────┐
    │  │                                       │  │                                     │
  1 │  │ [SEC Fetch] Fetching SEC EDGAR...     │  │                                     │
  2 │  │ [SEC Fetch] Successfully loaded...    │  │ ┌─ MetricTable ──────────────────┐  │
    │  │                                       │  │ │ Revenue    $215.9B    2025      │  │
    │  │                                       │  │ │ Net Income $120.1B    2025      │  │
    │  │                                       │  │ │ FCF        $96.7B     2025      │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
  3 │  │ [Health] Analyzing financial health... │  │                                     │
  4 │  │ [Health] Interest coverage: 507.34x   │  │                                     │
  5 │  │ [Health] Net margin: 55.6%            │  │                                     │
  6 │  │ [Health] Assessment: Strong           │  │ ┌─ FinancialHealthCard ───────────┐  │
    │  │                                       │  │ │ [Strong] ICR 507x D/E 0.31x    │  │
    │  │                                       │  │ │ Gross 71.1% | Op 60.4% | Net   │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │ ┌─ RevenueChart (Recharts) ───────┐  │
    │  │                                       │  │ │ ████ █████ █████████████████████ │  │
    │  │                                       │  │ │ 2007                       2025  │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
  7 │  │ [DCF] Building DCF model...           │  │                                     │
  8 │  │ [DCF] Growth rate: 30.0%              │  │                                     │
  9 │  │ [DCF] WACC: 10.66%                    │  │                                     │
 10 │  │ [DCF] Intrinsic value: $220.36        │  │ ┌─ FCFChart ─────────────────────┐  │
    │  │                                       │  │ │ ████ ████ ████ ░░░░ ░░░░ ░░░░  │  │
    │  │                                       │  │ │ hist                  projected │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │ ┌─ DCFResultCard ─────────────────┐  │
    │  │                                       │  │ │       $220.36 / share            │  │
    │  │                                       │  │ │ EV $5.4T  TV $9.1T  PV $2.1T   │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │ ┌─ ValuationGauge ────────────────┐  │
    │  │                                       │  │ │      $220.36 / share             │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │ ┌─ AssumptionSlider ──────────────┐  │
    │  │                                       │  │ │ Growth:    ──●────── 30.0%      │  │
    │  │                                       │  │ │ Discount:  ───●───── 10.7%      │  │
    │  │                                       │  │ │ Terminal:  ─●─────── 3.0%       │  │
    │  │                                       │  │ │ [ Recalculate DCF ]              │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
 11 │  │ [Trace] Tracing data points...        │  │                                     │
 12 │  │ [Trace] 70 points across 14 metrics   │  │ ┌─ SourceTable ──────────────────┐  │
    │  │                                       │  │ │ Revenue    $215.9B 2025  10-K ↗ │  │
    │  │                                       │  │ │ Net Income $120.1B 2025  10-K ↗ │  │
    │  │                                       │  │ │ ...                              │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │                                     │
    │  │ ● (cursor stops, stream complete)     │  │ ┌─ Verdict ──────────────────────┐  │
    │  │                                       │  │ │ NVIDIA CORP: Health Strong.     │  │
    │  │                                       │  │ │ DCF $220.36/share. 70 traced.   │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  └───────────────────────────────────────┘  └─────────────────────────────────────┘
```

### Phase 5: Interactive Recalculation (用户调参)

```
用户拖动滑块: Growth 30% → 15%, Discount 10.7% → 12%
    │
    ├── assumption-slider.tsx: onClick "Recalculate DCF"
    │
    ├── analysis-layout.tsx: handleRecalculate({
    │       ticker: "NVDA",
    │       growth_rate: 15.0,
    │       terminal_growth_rate: 3.0,
    │       discount_rate: 12.0,
    │   })
    │
    ├── POST http://localhost:8000/api/recalculate-dcf
    │   │
    │   ├── routes.py: recalculate_dcf()
    │   │   ├── get_cached_financials("NVDA")
    │   │   │   └── 从 _financials_cache 取出 (30分钟 TTL)
    │   │   │       └── 不需要重新调用 SEC API!
    │   │   │
    │   │   ├── compute_dcf(
    │   │   │       latest_fcf=96.7B,
    │   │   │       growth_rate=0.15,       # 用户调整
    │   │   │       terminal_growth_rate=0.03,
    │   │   │       discount_rate=0.12,     # 用户调整
    │   │   │       shares_outstanding=24.5B,
    │   │   │   )
    │   │   │   └── 重算: 新 intrinsic_value_per_share = $X.XX
    │   │   │
    │   │   └── 返回: {intrinsic_value_per_share, chart_data, ...}
    │   │
    │   └── ← 200 OK (同步响应, 毫秒级)
    │
    └── analysis-layout.tsx: setUpdatedComponents(...)
        ├── 更新 dcf_result_card: 新内在价值
        ├── 更新 valuation_gauge: 新仪表数值
        └── 更新 fcf_chart: 新预测柱状图
            └── 无需重新建立 SSE 连接, 页面局部刷新
```

---

## 4. Generative UI Protocol

后端通过 SSE 推送 JSON 指令, 前端通过组件注册表动态挂载 React 组件。这是 "白盒化" 的核心机制。

### 4.1 SSE Event Types

| Event Type | 方向 | 用途 |
|---|---|---|
| `agent_thinking` | Backend → Frontend | Agent 推理过程 (显示在 Terminal) |
| `component` | Backend → Frontend | 指示前端挂载一个 React 组件 |
| `step_complete` | Backend → Frontend | 节点完成通知 |
| `analysis_complete` | Backend → Frontend | 分析结束, 关闭 SSE 连接 |
| `error` | Backend → Frontend | 错误 (可恢复/不可恢复) |

### 4.2 Component Event Format

```json
{
    "event": "component",
    "component_type": "dcf_result_card",
    "props": {
        "entity_name": "NVIDIA CORP",
        "intrinsic_value_per_share": 220.36,
        "enterprise_value": 5401873342000.63,
        "terminal_value": 9113935315410.4,
        "pv_fcf_sum": 2090726006415.54,
        "assumptions": {
            "growth_rate": 30.0,
            "terminal_growth_rate": 3.0,
            "discount_rate": 10.66,
            "projection_years": 10,
            "latest_fcf": 96676000000.0
        }
    }
}
```

### 4.3 Component Registry

前端 `component-registry.ts` 维护类型到 React 组件的映射:

```
component_type          → React Component         → 数据来源
─────────────────────────────────────────────────────────────────
metric_table            → MetricTable             ← fetch_sec_data 节点
financial_health_card   → FinancialHealthCard     ← financial_health 节点
revenue_chart           → RevenueChart (Recharts) ← financial_health 节点
fcf_chart               → FCFChart (Recharts)     ← dcf_model 节点
dcf_result_card         → DCFResultCard           ← dcf_model 节点
valuation_gauge         → ValuationGauge          ← dcf_model 节点
assumption_slider       → AssumptionSlider        ← dcf_model 节点
source_table            → SourceTable             ← logic_trace 节点
```

所有组件通过 `React.lazy()` 懒加载, 配合 `<Suspense fallback={<Skeleton/>}>` 渲染。

### 4.4 Frontend Data Flow

```
EventSource
    ↓
useSSE (解析 JSON, 分类事件)
    ↓
useAnalysisStream (拆分为 thinkingMessages / components / verdict)
    ↓
AnalysisLayout
    ├── AgentTerminal ← thinkingMessages[]
    │   └── TypewriterText (逐字显示, 15ms/字, requestAnimationFrame)
    │       └── node 颜色标签: 蓝(SEC) 绿(Health) 黄(DCF) 紫(Trace)
    │
    └── Visualizer ← components[]
        └── 遍历 ComponentInstruction[]
            └── getComponent(type) → lazy React component
                └── <Component {...props} /> 渲染
```

---

## 5. Key Data Models

### 5.1 SEC Raw Response (`models/sec.py`)

```
SECCompanyFacts
├── cik: int                          # 1045810
├── entityName: str                   # "NVIDIA CORP"
└── facts: {namespace → {tag → SECFact}}
    └── "us-gaap"
        └── "Revenues" → SECFact
            ├── label: str | None
            ├── description: str | None
            └── units: SECFactUnits
                ├── USD: [SECFactEntry, ...]
                ├── USD/shares: [SECFactEntry, ...]  (EPS 等)
                └── shares: [SECFactEntry, ...]       (股数等)

SECFactEntry
├── start: str | None     # "2024-01-29" (期间起始, 可选)
├── end: str              # "2025-01-26" (期间结束)
├── val: float            # 215938000000
├── accn: str             # "0001045810-26-000021" (SEC 入档号)
├── fy: int               # 2026 (财务年度)
├── fp: str               # "FY" (全年)
├── form: str             # "10-K" (年报)
├── filed: str            # "2026-02-25"
└── frame: str | None     # "CY2025" 或 "CY2024Q4I" (去重键)
```

### 5.2 Normalized Financial Data (`models/financial.py`)

```
CompanyFinancials
├── cik, ticker, entity_name
└── 15 个 list[AnnualMetric] 字段:
    ├── revenue              ← TAG_MAP["revenue"] (5 个候选标签)
    ├── net_income           ← NetIncomeLoss
    ├── operating_income     ← OperatingIncomeLoss
    ├── total_assets         ← Assets (instant frame CYxxxxQ4I)
    ├── total_liabilities    ← Liabilities (instant frame)
    ├── stockholders_equity  ← StockholdersEquity (instant frame)
    ├── operating_cash_flow  ← NetCashProvidedByUsedInOperatingActivities
    ├── capital_expenditure  ← PaymentsToAcquire... (2 个候选)
    ├── free_cash_flow       ← 计算值: OCF - |CapEx|
    ├── interest_expense     ← InterestExpense
    ├── long_term_debt       ← LongTermDebt (instant frame)
    ├── cash_and_equivalents ← CashAndCashEquivalents... (instant frame)
    ├── diluted_eps          ← EarningsPerShareDiluted (单位: USD/shares)
    ├── diluted_shares       ← WeightedAverage... (单位: shares)
    └── cost_of_revenue      ← CostOfRevenue (3 个候选)

AnnualMetric
├── calendar_year: int     # 2025
├── value: float           # 215938000000.0
├── fiscal_year: int       # 2026 (NVIDIA 财年1月结束)
├── filing_date: str       # "2026-02-25"
├── sec_accession: str     # "0001045810-26-000021"
└── form: str              # "10-K"
```

### 5.3 LangGraph State (`models/agent_state.py`)

```
AnalysisState (TypedDict)
├── ticker: str                         # "NVDA" (输入, 不可变)
├── financials: CompanyFinancials|None   # Node 1 填充
├── fetch_errors: list[str]             # Node 1 填充 (如果失败)
├── health_metrics: dict | None         # Node 2 填充
├── health_assessment: str | None       # Node 2 填充 ("Strong")
├── dcf_result: dict | None             # Node 3 填充
├── source_map: dict | None             # Node 4 填充
├── reasoning_steps: list[str]          # 所有节点追加 (Annotated[list, add])
└── verdict: str | None                 # Node 4 填充
```

---

## 6. Critical Design Decisions

### 6.1 XBRL Tag Fallback with Best-Match Selection

**问题**: 不同公司使用不同的 XBRL 标签表达同一财务概念。NVIDIA 的 CapEx 在早期用 `PaymentsToAcquirePropertyPlantAndEquipment`, 近年改用 `PaymentsToAcquireProductiveAssets`。

**解决**: `_extract_annual_metrics` 遍历所有候选标签, 选择 `latest_year` 最大的 (而非第一个匹配)。这避免了旧标签只有历史数据而遮蔽新标签的问题。

### 6.2 Frame-Based Deduplication

**问题**: SEC API 对同一数据点返回多个条目 (原始报告 + 后续重述)。

**解决**: 只保留有 `frame` 字段的条目。frame 是 SEC 的规范去重键:
- `CY2024` = 日历年 2024 的全年 duration 值 (收入/利润等)
- `CY2024Q4I` = 日历年 2024 Q4 的 instant 值 (资产/负债等)
- `CY2024Q4` = 季度 period 值 → 过滤掉 (正则 `Q\d$`)

### 6.3 StreamWriter vs astream_events

**选择 StreamWriter**: LangGraph 的 `astream_events` 会产生大量内部回调事件, 难以过滤。`StreamWriter` 允许每个节点精确控制发射什么事件, 直接映射到 Generative UI 协议。

### 6.4 Separate Recalculation Endpoint

**问题**: 用户调整 DCF 参数后, 如果重新走 SSE 流, 需要重新调用 SEC API 和重跑所有节点。

**解决**: `POST /api/recalculate-dcf` 从内存缓存读取 `CompanyFinancials` (30分钟 TTL), 只重算 `compute_dcf()`, 毫秒级返回。前端局部更新 3 个组件 (dcf_result_card, valuation_gauge, fcf_chart)。

### 6.5 Lazy Component Registry

**原因**: Recharts 是重型图表库。8 个分析组件全部 `React.lazy()` 加载, 初始页面 bundle 不包含图表代码。组件按 SSE 事件到达顺序按需加载。

---

## 7. API Contract

### `GET /api/analyze/{ticker}` (SSE Stream)

Response: `text/event-stream`

事件产出顺序:

```
1.  event: agent_thinking   {node: "fetch_sec_data", content: "Fetching..."}
2.  event: agent_thinking   {node: "fetch_sec_data", content: "Successfully loaded..."}
3.  event: component        {component_type: "metric_table", props: {...}}
4.  event: step_complete    {node: "fetch_sec_data", summary: "Loaded 5 series..."}
5.  event: agent_thinking   {node: "financial_health_scan", content: "Analyzing..."}
6.  event: agent_thinking   {node: "financial_health_scan", content: "ICR: 507.34x"}
7.  event: agent_thinking   {node: "financial_health_scan", content: "Net margin: 55.6%"}
8.  event: agent_thinking   {node: "financial_health_scan", content: "Assessment: Strong"}
9.  event: component        {component_type: "financial_health_card", props: {...}}
10. event: component        {component_type: "revenue_chart", props: {...}}
11. event: step_complete    {node: "financial_health_scan", summary: "..."}
12. event: agent_thinking   {node: "dynamic_dcf", content: "Building DCF model..."}
13. event: agent_thinking   {node: "dynamic_dcf", content: "Growth rate: 30.0%"}
14. event: agent_thinking   {node: "dynamic_dcf", content: "WACC: 10.66%"}
15. event: agent_thinking   {node: "dynamic_dcf", content: "Intrinsic value: $220.36"}
16. event: component        {component_type: "fcf_chart", props: {...}}
17. event: component        {component_type: "dcf_result_card", props: {...}}
18. event: component        {component_type: "valuation_gauge", props: {...}}
19. event: component        {component_type: "assumption_slider", props: {...}}
20. event: step_complete    {node: "dynamic_dcf", summary: "..."}
21. event: agent_thinking   {node: "logic_trace", content: "Tracing..."}
22. event: agent_thinking   {node: "logic_trace", content: "Traced 70 data points..."}
23. event: component        {component_type: "source_table", props: {...}}
24. event: step_complete    {node: "logic_trace", summary: "..."}
25. event: analysis_complete {verdict: "...", ticker: "NVDA"}
```

### `POST /api/recalculate-dcf`

Request:
```json
{
    "ticker": "NVDA",
    "growth_rate": 15.0,
    "terminal_growth_rate": 3.0,
    "discount_rate": 12.0
}
```

Response:
```json
{
    "projected_fcf": [...],
    "terminal_value": ...,
    "enterprise_value": ...,
    "intrinsic_value_per_share": ...,
    "assumptions": {...},
    "chart_data": [
        {"year": 2021, "fcf": ..., "type": "historical"},
        {"year": 2026, "fcf": ..., "type": "projected"},
        ...
    ]
}
```

---

## 8. Error Handling

```
错误场景                     处理方式                              前端表现
─────────────────────────────────────────────────────────────────────────
Ticker 不存在               ErrorEvent(recoverable=False)        红色错误条
SEC API 超时/5xx            ErrorEvent(recoverable=False)        红色错误条
SEC API 429 (限速)          sec_client._rate_limit() 自动等待    用户无感
XBRL 标签不存在              字段返回空列表, 节点继续执行          指标显示 "N/A"
FCF 数据不足                 dcf_node 返回 None, 跳过图表         无 DCF 卡片
利息/负债数据缺失            WACC 回退到全权益模型                 正常显示
重算时缓存过期 (30min)       HTTP 404 + 错误提示                  需要重新分析
```

---

## 9. How to Run

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
# → http://localhost:3000
```

输入 Ticker (如 NVDA), 观察左侧 Agent 推理链实时展示, 右侧组件逐个挂载。
分析完成后拖动滑块调整假设参数, 点击重算即时看到估值变化。
