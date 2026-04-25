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
│                    (实时推送) │              (lazy load 9 组件)     │
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
│  │                      relative_valuation (相对估值)           │   │
│  │                                   │                          │   │
│  │                                   v                          │   │
│  │                        event_sentiment (消息面修正)           │   │
│  │                                   │                          │   │
│  │                                   v                          │   │
│  │                         event_impact (事件影响重算)            │   │
│  │                                   │                          │   │
│  │                                   v                          │   │
│  │                              strategy (买入点决策)            │   │
│  │                                   │                          │   │
│  │                                   v                          │   │
│  │                              logic_trace ──> END             │   │
│  └──────────────────────┬──────────────────────────────────────┘   │
│                         │                                           │
│                    StreamWriter                                     │
│                    (每个节点实时发射事件)                             │
│                         │                                           │
│  ┌──────────────────────v──────────────────────────────────────┐   │
│  │              Data Pipelines                                  │   │
│  │  ┌───────────────────────────────────────────┐               │   │
│  │  │ SEC Pipeline                               │               │   │
│  │  │ TickerResolver ──> SECClient ──> SECData   │               │   │
│  │  │ (ticker→CIK)      (EDGAR API)  (XBRL归一化)│               │   │
│  │  └───────────────────────────────────────────┘               │   │
│  │  ┌───────────────────────────────────────────┐               │   │
│  │  │ Market Data Pipeline (FMP /stable/ API)    │               │   │
│  │  │ MarketDataClient                           │               │   │
│  │  │ ├── get_current_price()    → 实时股价      │               │   │
│  │  │ ├── get_annual_closing...  → 年终收盘价    │               │   │
│  │  │ ├── get_peers()            → 同业股票代码  │               │   │
│  │  │ ├── get_peer_key_metrics() → TTM 估值乘数  │               │   │
│  │  │ └── get_batch_peer_metrics() → 批量并发    │               │   │
│  │  └───────────────────────────────────────────┘               │   │
│  │  ┌───────────────────────────────────────────┐               │   │
│  │  │ Event & Sentiment Pipeline                 │               │   │
│  │  │ FinnhubClient (Free plan)                  │               │   │
│  │  │ ├── get_company_news()    → 30天新闻       │               │   │
│  │  │ │   (7天分批获取, 去重排序)                  │               │   │
│  │  │ ├── get_news_sentiment()  → Premium情绪     │               │   │
│  │  │ └── get_insider_sentiment() → 内部人情绪    │               │   │
│  │  │ LLMSentiment (DeepSeek)                    │               │   │
│  │  │ └── analyze_news_sentiment() → LLM情绪打分  │               │   │
│  │  │ EventImpact (两步LLM)                      │               │   │
│  │  │ ├── Step1: 筛选有估值影响的新闻              │               │   │
│  │  │ └── Step2: 分析参数调整 → DCF重算           │               │   │
│  │  └───────────────────────────────────────────┘               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    v                     v
          ┌─────────────────┐   ┌──────────────────────┐
          │  SEC EDGAR API   │   │  FMP API              │   ┌──────────────────┐
          │  data.sec.gov    │   │  financialmodelingprep │   │  Finnhub + LLM   │
          │  (XBRL/JSON)     │   │  (股价/历史行情)       │   │  (新闻/情绪分析)  │
          └─────────────────┘   └──────────────────────┘   └──────────────────┘
```

---

## 2. Directory Structure

```
alpha/
├── backend/
│   ├── pyproject.toml                          # Python 依赖定义
│   ├── backend/
│   │   ├── main.py                             # FastAPI 入口 + lifespan 管理
│   │   ├── config.py                           # pydantic-settings 配置 (自动发现 .env)
│   │   ├── models/
│   │   │   ├── sec.py                          # SEC EDGAR 原始响应模型
│   │   │   ├── financial.py                    # 归一化后的财务指标模型
│   │   │   ├── agent_state.py                  # LangGraph TypedDict 状态
│   │   │   └── events.py                       # SSE 事件模型 (Generative UI 协议)
│   │   ├── services/
│   │   │   ├── ticker_resolver.py              # Ticker → CIK 映射
│   │   │   ├── sec_client.py                   # EDGAR HTTP 客户端 (httpx)
│   │   │   ├── sec_agent.py                    # XBRL 归一化层 (核心领域逻辑)
│   │   │   ├── market_data.py                  # FMP 市场行情客户端 (httpx)
│   │   │   ├── finnhub_client.py               # Finnhub 新闻/内部人情绪客户端
│   │   │   └── llm_sentiment.py                # DeepSeek LLM 新闻情绪分析
│   │   ├── agents/
│   │   │   ├── value_analyst.py                # LangGraph StateGraph 编排
│   │   │   └── nodes/
│   │   │       ├── financial_health.py         # 节点1: 财务健康扫描
│   │   │       ├── dcf_model.py                # 节点2: 动态 DCF 建模
│   │   │       ├── relative_valuation.py       # 节点3: 相对估值 (市场乘数, 主节点)
│   │   │       ├── relative_valuation_math.py  # 节点3: 纯计算函数 (无I/O)
│   │   │       ├── event_sentiment.py          # 节点4: 消息面情绪分析 (主节点)
│   │   │       ├── event_sentiment_math.py     # 节点4: 纯计算函数 (无I/O)
│   │   │       ├── event_impact.py             # 节点5: 事件影响分析 (两步LLM+DCF重算)
│   │   │       ├── event_impact_math.py        # 节点5: 纯计算函数 (参数注册表/调整/重算)
│   │   │       ├── strategy.py                 # 节点6: 安全边际 & 买入策略
│   │   │       └── logic_trace.py              # 节点7: 数据溯源
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
        │       ├── relative-valuation-card.tsx  # 相对估值卡片 (乘数+百分位+同业)
        │       ├── strategy-dashboard.tsx       # 估值热力仪表盘 (买入策略)
        │       ├── sentiment-card.tsx           # 消息面情绪卡片 (仪表+新闻+内部人)
        │       ├── event-impact-card.tsx       # 事件影响卡片 (参数对比+DCF重算+触发事件)
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
    ├── market_data_client (FMP /stable/ API httpx 客户端)
    │   └── 需要环境变量 AQ_FMP_API_KEY (可在 .env 设置, 未设置则市场数据功能跳过)
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
    │                                              relative_valuation (相对估值)
    │                                                   │
    │                                                   v
    │                                              event_sentiment (消息面情绪)
    │                                                   │
    │                                                   v
    │                                              event_impact (事件影响+DCF重算)
    │                                                   │
    │                                                   v
    │                                              strategy (买入策略)
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
    │       relative_valuation_result: None,   # 节点3填充 (相对估值)
    │       event_sentiment_result: None,      # 节点4填充 (消息面情绪)
    │       event_impact_result: None,         # 节点5填充 (事件影响+DCF重算)
    │       strategy_result: None,
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

#### Node 4: `relative_valuation` (相对估值 — 市场乘数法)

```
relative_valuation_node(state, writer)
    │
    ├── 前置检查: financials 必须存在, 否则返回空结果
    │
    ├── 获取实时市场价格:
    │   ├── market_data_client.get_current_price("NVDA")
    │   │   └── GET /stable/quote?symbol=NVDA&apikey=KEY
    │   │       └── 返回: [{"symbol":"NVDA","price":110.93,...}]
    │   └── 失败 → 返回 {price_available: false}, 前端显示提示横幅
    │
    ├── 计算当前乘数 (_compute_current_multiples):
    │   ├── Market Cap = price × diluted_shares
    │   ├── Enterprise Value = market_cap + long_term_debt - cash
    │   ├── P/E = price / EPS (EPS > 0)
    │   ├── P/B = market_cap / equity (equity > 0)
    │   ├── P/S = market_cap / revenue (revenue > 0)
    │   ├── EV/Revenue, EV/EBIT, EV/FCF
    │   └── PEG = P/E / (EPS CAGR% × 100) — 3年EPS复合增长率
    │
    ├── 计算历史百分位 (_compute_historical_multiples):
    │   ├── get_annual_closing_prices("NVDA", years=10)
    │   │   └── GET /stable/historical-price-eod/full?symbol=NVDA&from=...&apikey=KEY
    │   ├── 对每年有 SEC 数据 + 价格数据的年份, 计算 P/E, P/B, P/S, EV/Rev, EV/EBIT
    │   ├── 计算 median, average, count
    │   └── percentile_rank(current, historical_series) → 当前值在历史中的百分位
    │
    ├── 同业对比 (_fetch_peer_data):
    │   ├── get_peers("NVDA") → ["AMD","INTC","AVGO","QCOM",...]
    │   │   └── GET /stable/stock-peers?symbol=NVDA&apikey=KEY
    │   ├── get_batch_peer_metrics(peers)
    │   │   └── 并发调用 get_peer_key_metrics_ttm() (asyncio.gather)
    │   │       └── GET /stable/ratios-ttm?symbol=AMD&apikey=KEY
    │   │           └── 提取: priceToEarningsRatioTTM, priceToBookRatioTTM, ...
    │   ├── 计算同行中位数 (peRatio, pbRatio, ...)
    │   └── delta% = (company_value - peer_median) / peer_median × 100
    │
    ├── 降级策略:
    │   ├── 无 FMP Key → price_available=false, 跳过所有价格依赖计算
    │   ├── 有 Key 但无同业 → peer_data_available=false, 隐藏同业表格
    │   └── 完整数据 → 全部分析 (当前乘数 + 历史百分位 + 同业偏差)
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 5 (价格/乘数/历史/同业/偏差)
    │   ├── ComponentEvent("relative_valuation_card", {
    │   │       entity_name, ticker, price_available,
    │   │       current_multiples: {pe, pb, ps, ev_to_revenue, ...},
    │   │       historical_stats: {pe: {series, median, average}, ...},
    │   │       percentiles: {pe: 70.0, ...},
    │   │       peer_comparison: {peer_data_available, peers, peer_medians, deltas},
    │   │   })
    │   │   └── 前端挂载 RelativeValuationCard:
    │   │       ├── A区: 当前乘数网格 (4×2) + 百分位指示器 + 同业偏差%
    │   │       ├── B区: 历史百分位条形图 (颜色: <20绿, 20-50蓝, 50-80琥珀, >80红)
    │   │       └── C区: 同业对比表 (目标公司行 + 同业行 + 中位数行)
    │   └── StepCompleteEvent
    │
    └── return {relative_valuation_result: {...}, reasoning_steps}
```

#### Node 5: `event_sentiment` (消息面情绪分析)

```
event_sentiment_node(state, writer)
    │
    ├── 前置检查: financials 必须存在, AQ_FINNHUB_API_KEY 必须设置
    │   └── 缺失则跳过: 发射 StepCompleteEvent, return None
    │
    ├── 获取公司新闻:
    │   ├── finnhub_client.get_company_news("NVDA", days=30)
    │   │   └── 分7天批次并发获取 GET /company-news (semaphore=3)
    │   │       └── 返回: [{headline, summary, source, datetime, url}, ...]
    │   │       └── 按 id 去重, 按 datetime DESC 排序
    │   └── 相关度过滤 (event_sentiment_math.py):
    │       ├── 评分: 4(标题含ticker/公司名) 3(summary+related) 2(唯一related) 0(排除)
    │       ├── TICKER_ALIASES 公司名匹配 (NVDA→"nvidia", AAPL→"apple" 等 40+)
    │       ├── 双排序: 相关度 DESC, 日期 DESC, 最多保留 30 篇
    │       └── 权威来源白名单过滤 (Reuters/Bloomberg/WSJ/FT 等 20+)
    │
    ├── 获取 SEC 8-K 文件:
    │   ├── sec_client.get_recent_8k_filings(cik, days=30)
    │   │   └── EDGAR full-text search → 8-K filings → 转为 article 格式
    │   └── 预置到文章列表 (SEC 文件始终视为权威)
    │
    ├── 尝试 Finnhub Premium 情绪数据:
    │   ├── finnhub_client.get_news_sentiment("NVDA")
    │   │   └── GET /news-sentiment?symbol=NVDA&token=KEY
    │   │       └── Free plan → HTTP 403 → 返回 None
    │   └── Premium 不可用时, 使用 LLM 降级分析
    │
    ├── LLM 新闻情绪分析 (DeepSeek, OpenAI 兼容 API):
    │   ├── llm_sentiment.analyze_news_sentiment("NVDA", articles[:20])
    │   │   └── POST {AQ_LLM_BASE_URL}/chat/completions
    │   │       └── System prompt 要求返回结构化 JSON:
    │   │           {articles: [{sentiment, event_type, confidence}],
    │   │            overall_score: float, summary: str, key_events: [str]}
    │   ├── 使用 XML 标签 <articles> 包裹新闻内容 (防止 prompt injection)
    │   └── _validate_llm_response() 校验返回值 (不修改原 dict): 限制 overall_score ∈ [-1, 1],
    │       confidence ∈ [0, 1], key_events ≤ 5 条
    │
    ├── 获取内部人情绪:
    │   └── finnhub_client.get_insider_sentiment("NVDA", months=3)
    │       └── GET /stock/insider-sentiment?symbol=NVDA&from=...&to=...&token=KEY
    │           └── 提取 MSPR (Monthly Share Purchase Ratio) 和 net change
    │
    ├── 综合情绪评分 (event_sentiment_math.py):
    │   ├── compute_overall_sentiment(news_score, insider_score, ...)
    │   │   └── 权重: 60% 新闻 + 40% 内部人 (两者都有时)
    │   │       └── 只有新闻 → 100% 新闻; 只有内部人 → 100% 内部人
    │   ├── _sentiment_label(score) → "Very Bearish"/"Bearish"/"Neutral"/"Bullish"/"Very Bullish"
    │   └── compute_sentiment_adjustment(overall):
    │       ├── score < -0.5 → delta = -8% (提高买入门槛)
    │       ├── score < -0.2 → delta = -4%
    │       ├── score > 0.5 → delta = +5% (降低买入门槛)
    │       ├── score > 0.2 → delta = +3%
    │       └── else → delta = 0%
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 5 (新闻获取/LLM分析/内部人/综合评分)
    │   ├── ComponentEvent("sentiment_card", {
    │   │       ticker, overall_sentiment, sentiment_label,
    │   │       news_score, insider_score, insider_mspr, insider_net_change,
    │   │       sentiment_adjustment: {margin_of_safety_pct_delta, reasoning},
    │   │       articles: [{headline, sentiment, event_type, confidence, ...}],
    │   │       llm_summary, key_events,
    │   │   })
    │   │   └── 前端挂载 SentimentCard:
    │   │       ├── A区: 半圆仪表盘 (bearish红 → neutral黄 → bullish绿)
    │   │       ├── B区: 新闻细分 (看多/中性/看空分布条 + 关键事件 + 文章列表)
    │   │       └── C区: 内部人情绪 (MSPR 进度条 + 净变动)
    │   └── StepCompleteEvent
    │
    └── return {event_sentiment_result: {...}, reasoning_steps}
```

#### Node 5b: `event_impact` (事件影响分析 + DCF 重算)

```
event_impact_node(state, writer)
    │
    ├── 前置检查: financials, event_sentiment_result.articles, dcf_result 必须存在
    │   ├── LLM API key 未设置 → 跳过 (优雅降级)
    │   └── 缺失任一 → 发射 StepCompleteEvent, return None
    │
    ├── 提取原始 DCF 假设:
    │   └── {growth_rate, terminal_growth_rate, discount_rate, latest_fcf}
    │
    ├── LLM Call 1 — 筛选有影响的新闻:
    │   ├── 输入: event_sentiment_result.articles (已过滤的权威来源文章)
    │   ├── Prompt 要求排除: 常规分析师评级、泛市场评论、已定价业绩报告
    │   └── 输出: {"impactful_indices": [0, 3, 5], "reasoning": "..."}
    │       └── 无影响文章 → return None ("no material events found")
    │
    ├── LLM Call 2 — 参数影响分析:
    │   ├── 输入: 筛选后文章 + 当前 DCF 假设
    │   ├── 可调参数: growth_rate, terminal_growth_rate, discount_rate,
    │   │             risk_adjustment→WACC, revenue_adjustment→增长, margin_adjustment→增长*0.5,
    │   │             fcf_one_time_adjust→FCF
    │   ├── 保守原则: 仅建议高置信度调整
    │   └── 输出: {adjustments: {param: {type, value, reasoning}|null, ...},
    │              summary, confidence}
    │
    ├── 应用参数调整 (event_impact_math.py):
    │   ├── apply_all_adjustments(original, adjustments)
    │   │   ├── delta → 累加; multiplier → 相乘; absolute → 替换
    │   │   └── 最终 clamp 到 PARAMETER_REGISTRY 中的 min/max
    │   └── recalculate_dcf(adjusted, shares_outstanding)
    │       └── 直接调用 dcf_model.compute_dcf() 重算
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 3 (筛选/分析/重算)
    │   ├── ComponentEvent("event_impact_card", {
    │   │       ticker, original_assumptions, parameter_adjustments,
    │   │       adjusted_assumptions, recalculated_dcf,
    │   │       impactful_articles: [{headline, source, url, date, ...}],
    │   │       summary, confidence,
    │   │   })
    │   │   └── 前端挂载 EventImpactCard:
    │   │       ├── 摘要 + 置信度指示器
    │   │       ├── 参数对比表 (Original → Adjusted + delta)
    │   │       ├── 重算内在价值 (新 DCF 结果)
    │   │       └── 触发事件列表 (可点击链接 + 日期)
    │   └── StepCompleteEvent
    │
    └── return {event_impact_result: {...}, reasoning_steps}
```

#### Node 6: `strategy` (安全边际 & 买入策略)

```
strategy_node(state, writer)
    │
    ├── 前置检查: financials 和 dcf_result.intrinsic_value_per_share 必须存在
    │   └── 缺失则跳过: 发射 StepCompleteEvent("Strategy skipped"), return None
    │
    ├── 决定使用哪个内在价值:
    │   ├── 优先使用 event_impact_result.recalculated_dcf.intrinsic_value_per_share (如存在)
    │   └── 否则回退到原始 dcf_result.intrinsic_value_per_share
    │
    ├── 获取实时市场价格:
    │   ├── market_data_client.get_current_price("NVDA")
    │   │   └── GET /stable/quote?symbol=NVDA&apikey=KEY
    │   │       └── 返回: [{"symbol":"NVDA","price":110.93,...}]
    │   └── current_price = $110.93
    │       └── 失败或 ≤ 0 则跳过 (优雅降级, 不阻塞后续节点)
    │
    ├── 计算安全边际 (Margin of Safety):
    │   ├── mos_pct = (intrinsic - current_price) / intrinsic × 100
    │   │   └── ($220.36 - $110.93) / $220.36 × 100 = 49.7%
    │   ├── suggested_entry = intrinsic × 0.85 = $187.31 (15% 安全边际)
    │   ├── upside_pct = (intrinsic - current_price) / current_price × 100
    │   │   └── ($220.36 - $110.93) / $110.93 × 100 = 98.7%
    │   └── signal = _determine_signal(mos_pct):
    │       ├── > 25%  → "Deep Value"    ← 此例 49.7%
    │       ├── > 10%  → "Undervalued"
    │       ├── > -10% → "Fair Value"
    │       └── else   → "Overvalued"
    │
    ├── 计算 P/E 历史分位数:
    │   ├── market_data_client.get_annual_closing_prices("NVDA", years=10)
    │   │   └── GET /stable/historical-price-eod/full?symbol=NVDA&from=2016-04-14&apikey=KEY
    │   │       └── 返回每年最后交易日收盘价 (使用原始 close, 非 adjClose)
    │   │
    │   ├── 交叉匹配: 年终股价 × SEC diluted_eps → 每年 P/E
    │   │   ├── 使用 raw close + raw EPS → P/E 对股票拆分不变 (P/E invariant)
    │   │   └── 只计算 EPS > 0 的年份 (亏损年跳过)
    │   │
    │   ├── current_pe = current_price / latest_eps
    │   │   └── $110.93 / $4.90 = 22.6x
    │   │
    │   └── pe_percentile = rank(current_pe) / count × 100
    │       └── 当前 P/E 在过去 N 年中所处位置 (需 ≥ 3 年数据)
    │
    ├── 相对估值交叉校验:
    │   ├── 读取 relative_valuation_result (从参数传入)
    │   ├── 若同业 P/E 偏差 < -20%: "P/E显著低于同行, 支持低估判断"
    │   ├── 若同业 P/E 偏差 > +20%: "P/E显著高于同行, 估值溢价需谨慎"
    │   └── 否则: "P/E大致与同行一致"
    │
    ├── 情绪修正 (来自 event_sentiment 节点):
    │   ├── 读取 event_sentiment_result (从参数传入)
    │   ├── 提取 sentiment_adjustment.margin_of_safety_pct_delta
    │   ├── delta != 0 时: 调整安全边际 = mos_pct + delta
    │   └── 推理链追加: "Sentiment adjustment: {reasoning} (Δ{delta}%)"
    │
    │  注: 两层调整分离 — event_impact 建模基本面影响 (DCF参数调整),
    │      sentiment 调整捕捉市场情绪 (粗粒度 MoS 修正), 两者叠加
    │
    ├── writer 发射事件:
    │   ├── AgentThinkingEvent × 5 (价格/MoS/信号/P/E)
    │   ├── ComponentEvent("strategy_dashboard", {
    │   │       entity_name, ticker, current_price, intrinsic_value,
    │   │       margin_of_safety_pct, suggested_entry_price, upside_pct,
    │   │       signal, current_pe, pe_percentile, historical_pe,
    │   │       sentiment_delta, sentiment_note,
    │   │   })
    │   │   └── 前端挂载 StrategyDashboard: 估值热力仪表盘
    │   │       ├── Signal 徽章 (绿/黄/红)
    │   │       ├── 三列价格对比: 市价 | 内在价值 | 建议买入价
    │   │       ├── 估值温度计 (CSS 渐变 red→amber→green + 标记线)
    │   │       ├── 安全边际% + 上行/下行空间%
    │   │       ├── P/E 分位数进度条 (历史百分位)
    │   │       └── 买入策略文字建议
    │   └── StepCompleteEvent
    │
    └── return {strategy_result: {...}, reasoning_steps}
```

#### Node 7: `logic_trace` (数据溯源)

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
    │        Event sentiment: Bullish (score: 0.45).
    │        Market multiples: P/E 22.6x, P/B 65.1x, P/S 28.4x.
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
SSE 事件流时序 (共约 25 个事件):
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
 11 │  │ [RelVal] Computing relative valuation... │  │                                     │
    │  │                                       │  │ ┌─ RelativeValuationCard ──────────┐│
 12 │  │ [RelVal] P/E 22.6, P/B 65.1, P/S 28  │  │ │ P/E 22.6x  P/B 65.1x  P/S 28.4x ││
 13 │  │ [RelVal] P/E at 35th pct (10yr)      │  │ │ ██████░░░░ 35th percentile       ││
 14 │  │ [RelVal] Peer PE median 28.4 (+26%)  │  │ │ 同业: AMD INTC AVGO QCOM...     ││
    │  │                                       │  │ └─────────────────────────────────┘│
 15 │  │ [Sentiment] Analyzing event sentiment │  │                                     │
 16 │  │ [Sentiment] Found 20 articles         │  │ ┌─ SentimentCard ─────────────────┐ │
    │  │ [Sentiment] Bullish (score: 0.45)     │  │ │ 仪表盘: bullish绿                │ │
    │  │                                       │  │ │ 新闻列表 + 内部人 MSPR          │ │
    │  │                                       │  │ └─────────────────────────────────┘ │
 17 │  │ [Impact] Screening articles...        │  │                                     │
 18 │  │ [Impact] 3 impactful articles found   │  │ ┌─ EventImpactCard ───────────────┐ │
    │  │ [Impact] Growth +2%, WACC +0.5%       │  │ │ Original → Adjusted 参数对比     │ │
    │  │                                       │  │ │ 重算: $215.42/share              │ │
    │  │                                       │  │ │ 触发事件 (可点击链接)            │ │
    │  │                                       │  │ └─────────────────────────────────┘ │
 19 │  │ [Strategy] Fetching market price...   │  │                                     │
 16 │  │ [Strategy] Price $110.93 vs $220.36   │  │                                     │
 17 │  │ [Strategy] MoS 49.7%. Deep Value      │  │                                     │
 18 │  │ [Strategy] P/E 22.6 at 35th pctl      │  │ ┌─ StrategyDashboard ─────────────┐ │
    │  │                                       │  │ │ [Deep Value]                     │ │
    │  │                                       │  │ │ $110.93  |  $220.36  |  $187.31  │ │
    │  │                                       │  │ │ ██████████████▌░░░░░░░ 温度计    │ │
    │  │                                       │  │ │ MoS +49.7%    Upside +98.7%     │ │
    │  │                                       │  │ │ P/E 22.6x ████░░░░ 35th pctl    │ │
    │  │                                       │  │ │ "深度价值区, 当前价格远低于..."    │ │
    │  │                                       │  │ └─────────────────────────────────┘ │
 19 │  │ [Trace] Tracing data points...        │  │                                     │
 20 │  │ [Trace] 70 points across 14 metrics   │  │ ┌─ SourceTable ──────────────────┐  │
    │  │                                       │  │ │ Revenue    $215.9B 2025  10-K ↗ │  │
    │  │                                       │  │ │ Net Income $120.1B 2025  10-K ↗ │  │
    │  │                                       │  │ │ ...                              │  │
    │  │                                       │  │ └─────────────────────────────────┘  │
    │  │                                       │  │                                     │
    │  │ ● (cursor stops, stream complete)     │  │ ┌─ Verdict ──────────────────────┐  │
    │  │                                       │  │ │ NVIDIA CORP: Health Strong.     │  │
    │  │                                       │  │ │ DCF $220.36/share.             │  │
    │  │                                       │  │ │ P/E 22.6x P/B 65.1x P/S 28.4x │  │
    │  │                                       │  │ │ 70 traced to SEC EDGAR.        │  │
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
        ├── 更新 fcf_chart: 新预测柱状图
        └── 更新 strategy_dashboard: 前端重算安全边际/信号/建议买入价
            ├── mosPct = (newIntrinsic - currentPrice) / newIntrinsic × 100
            ├── signal 阈值与后端 _determine_signal 一致
            ├── P/E 分位数不变 (不依赖 DCF 假设)
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
relative_valuation_card → RelativeValuationCard   ← relative_valuation 节点
sentiment_card          → SentimentCard           ← event_sentiment 节点
event_impact_card       → EventImpactCard         ← event_impact 节点
strategy_dashboard      → StrategyDashboard       ← strategy 节点
source_table            → SourceTable             ← logic_trace 节点
```

所有组件通过 `React.lazy()` 懒加载, 配合 `<Suspense fallback={<Skeleton/>}>` 渲染。共12个组件。

> **注**: `strategy_dashboard` 在用户调整 DCF 假设时, 由前端直接重算安全边际/信号 (无需请求后端), 保持与 DCF 卡片的数据一致性。

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
    │       └── node 颜色标签: 蓝(SEC) 绿(Health) 黄(DCF) 玫红(Strategy) 紫(Trace)
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
├── relative_valuation_result: dict|None # Node 4 填充 (市场乘数+百分位+同业)
├── event_sentiment_result: dict|None   # Node 5 填充 (消息面情绪+内部人+MoS修正)
├── event_impact_result: dict|None      # Node 5b 填充 (事件影响+参数调整+DCF重算)
├── strategy_result: dict | None        # Node 6 填充 (安全边际/P/E/信号+情绪修正)
├── source_map: dict | None             # Node 7 填充
├── reasoning_steps: list[str]          # 所有节点追加 (Annotated[list, add])
└── verdict: str | None                 # Node 7 填充
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

### 6.5 FMP /stable/ API 作为市场数据源 & 优雅降级

**问题**: DCF 计算的内在价值需要与实时市场价格对比, 才能给出买入建议。但项目原本只有 SEC EDGAR 基本面数据, 没有股价来源。

**选型**: Financial Modeling Prep (FMP) API, 通过现有 `httpx` 调用, 零新增依赖。
- FMP 于 2025年8月废弃了 `/api/v3/` 和 `/api/v4/` 端点, 现在使用 `/stable/` 端点
- 对比 `yfinance`: 会引入 pandas/numpy 重型依赖, 且为同步库, 与项目全 async 架构冲突
- 对比 Yahoo Finance 直连: 无官方 API, 端点频繁变更, 不稳定

**端点映射 (v3/v4 → stable)**:

| 功能 | 旧端点 (已废弃) | 新端点 (当前) |
|------|------------------|---------------|
| 实时报价 | `/api/v3/quote-short/{ticker}` | `/stable/quote?symbol=` |
| 历史行情 | `/api/v3/historical-price-full/{ticker}` | `/stable/historical-price-eod/full?symbol=` |
| 同业公司 | `/api/v4/stock_peers?symbol=` | `/stable/stock-peers?symbol=` |
| TTM 指标 | `/api/v3/key-metrics-ttm/{ticker}` | `/stable/ratios-ttm?symbol=` |

**降级策略**: `relative_valuation` 和 `strategy` 节点均设计为可选, 不阻塞主分析流程:
- API Key 未设置 (`AQ_FMP_API_KEY=""`) → `get_current_price()` 返回 None → `relative_valuation` 返回 `price_available=false`, `strategy` 跳过
- FMP 超时/错误 → 内部 try/except 捕获, 返回 None → 同上
- 有 Key 但无同业 → `peer_data_available=false`, 前端隐藏同业表格
- 节点 `ErrorEvent(recoverable=True)` → SSE 连接不关闭, 后续 `logic_trace` 正常执行
- 最终效果: 用户正常看到 DCF 估值, 只是没有相对估值卡片和策略仪表盘

### 6.6 Lazy Component Registry

**原因**: Recharts 是重型图表库。10 个分析组件全部 `React.lazy()` 加载, 初始页面 bundle 不包含图表代码。组件按 SSE 事件到达顺序按需加载。

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
21. event: agent_thinking   {node: "relative_valuation", content: "Computing relative valuation..."}
22. event: agent_thinking   {node: "relative_valuation", content: "Market cap: $2.7T | EV: $2.7T..."}
23. event: agent_thinking   {node: "relative_valuation", content: "Historical multiples computed..."}
24. event: agent_thinking   {node: "relative_valuation", content: "Found 5 peers: AMD, INTC, AVGO..."}
25. event: agent_thinking   {node: "relative_valuation", content: "Peer comparison deltas: pe: +26%..."}
26. event: component        {component_type: "relative_valuation_card", props: {...}}
27. event: step_complete    {node: "relative_valuation", summary: "..."}
28. event: agent_thinking   {node: "event_sentiment", content: "Analyzing event sentiment..."}
29. event: agent_thinking   {node: "event_sentiment", content: "Found 20 authoritative articles..."}
30. event: agent_thinking   {node: "event_sentiment", content: "Overall sentiment: Bullish (score: 0.45)"}
31. event: component        {component_type: "sentiment_card", props: {...}}
32. event: step_complete    {node: "event_sentiment", summary: "..."}
33. event: agent_thinking   {node: "event_impact", content: "Analyzing event impact on valuation..."}
34. event: agent_thinking   {node: "event_impact", content: "Screening 20 articles for valuation-relevant events..."}
35. event: agent_thinking   {node: "event_impact", content: "Found 3 articles with valuation impact..."}
36. event: component        {component_type: "event_impact_card", props: {...}}
37. event: step_complete    {node: "event_impact", summary: "..."}
38. event: agent_thinking   {node: "strategy", content: "Fetching current market price..."}
39. event: agent_thinking   {node: "strategy", content: "Price $110.93 vs intrinsic $220.36..."}
40. event: agent_thinking   {node: "strategy", content: "Computing historical P/E percentile..."}
41. event: agent_thinking   {node: "strategy", content: "Current P/E 22.6 at 35th percentile..."}
42. event: agent_thinking   {node: "strategy", content: "P/E roughly in line with peers."}
43. event: component        {component_type: "strategy_dashboard", props: {...}}
44. event: step_complete    {node: "strategy", summary: "..."}
45. event: agent_thinking   {node: "logic_trace", content: "Tracing..."}
46. event: agent_thinking   {node: "logic_trace", content: "Traced 70 data points..."}
47. event: component        {component_type: "source_table", props: {...}}
48. event: step_complete    {node: "logic_trace", summary: "..."}
49. event: analysis_complete {verdict: "...", ticker: "NVDA"}
```

### `POST /api/recalculate-dcf`

**校验**: `discount_rate` 必须 > `terminal_growth_rate`，否则返回 422。

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
FMP API Key 未设置           relative_valuation: price_available  显示"数据不可用"横幅
                             =false; strategy 节点跳过            无策略仪表盘
FMP API 超时/5xx            get_current_price 返回 None          同上
FMP 返回未知 ticker          响应为空列表, 返回 None              同上
FMP 无同业数据               peer_data_available=false            隐藏同业表格
Finnhub API Key 未设置       event_sentiment 节点跳过, 不阻塞      无情绪卡片
Finnhub Free plan            news-sentiment 返回 403, 使用 LLM    用户无感
DeepSeek/LLM 不可用          LLM 返回 None, 使用关键词分类         情绪仅基于内部人
Finnhub 无新闻数据           articles 为空, news_score 为 None     仅内部人情绪
Finnhub 无内部人数据          insider_data 为 None                  仅新闻情绪
event_impact 无前提数据       节点跳过, strategy 用原始 DCF         无事件影响卡片
event_impact LLM 不可用       节点跳过, 不阻塞 strategy             无事件影响卡片
event_impact 无重大事件       return None ("no material events")    无事件影响卡片
EPS 为负 (亏损公司)          P/E 分位数跳过, 仅显示安全边际       无 P/E 区域
strategy 节点异常            ErrorEvent(recoverable=True)         无策略仪表盘, 分析继续
重算时缓存过期 (30min)       HTTP 404 + 错误提示                  需要重新分析
```

---

## 9. How to Run

```bash
# 配置: 项目根目录 .env 文件 (自动发现, 无需手动 export)
# AQ_FMP_API_KEY=your_fmp_api_key    # 可选: 启用市场数据功能
# AQ_FINNHUB_API_KEY=your_key        # 可选: 启用消息面情绪分析
# AQ_LLM_API_KEY=your_key            # 可选: 启用 LLM 新闻情绪 (DeepSeek)
# AQ_LLM_BASE_URL=https://api.deepseek.com
# AQ_LLM_MODEL=deepseek-chat

# 首次配置
cd backend
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

cd frontend
npm install

# Terminal 1: Backend
cd backend
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
# → http://localhost:3000
```

输入 Ticker (如 NVDA), 观察左侧 Agent 推理链实时展示, 右侧组件逐个挂载。
分析完成后拖动滑块调整假设参数, 点击重算即时看到估值变化 (策略仪表盘同步更新)。

> **以下章节覆盖 v0.5 — v0.7 的新增内容（Phase 1 / 2 / 3）。** v0.4 之前的内容保持上方不变。

---

## 11. Phase 1 — LLM 基础设施 + 成本围栏（v0.5.0）

把 v0.3 / v0.4 中分散的 LLM 调用收编到统一框架，并叠加三层成本围栏防止生产事故。

### 11.1 统一 LLM 调用栈

```
backend/backend/services/llm/
├── client.py        # LLMClient.complete_json(prompt_name, variables, response_model, task_tag)
├── providers.py     # OpenAICompatibleProvider（DeepSeek / OpenAI / 任何兼容协议）
├── sanitize.py      # 输入净化 + 注入检测 + <<<USER_CONTENT>>> 边界包裹
├── accounting.py    # AccountingStore：每次调用结构化日志 + 24h 滑动窗成本聚合
├── budget.py        # BudgetGate：双闸熔断（global + per-IP）
└── errors.py        # LLMError 基类 + LLMConfigError / LLMProviderError / LLMParseError / LLMBudgetExceeded
```

调用流：

```
节点代码
   │ LLMClient.complete_json(prompt_name="thesis", variables={...}, response_model=InvestmentThesis, task_tag="thesis")
   ▼
1. load_prompt(name, version)              ← 读 YAML，缓存
2. template.user.format(**variables)
3. sanitize_text / sanitize_list           ← HTML escape + 边界包裹
4. BudgetGate.check(client_ip)             ← 双闸熔断（详见 11.3）
5. provider.chat_completion(...)           ← OpenAI 协议 HTTPS 调用
6. retry once on 429 / 5xx / parse error
7. response_model.model_validate(parsed)   ← Pydantic 校验
8. AccountingStore.record(client_ip,...)   ← 落 JSON 日志一行
   ▼
返回 BaseModel 实例（或 raise LLMError → 节点降级）
```

**关键不变性**：全站唯一入口；所有 LLM 调用都过这条流水线，没有节点能"偷偷直连 httpx"。

### 11.2 Prompt 库

`backend/backend/prompts/<name>_v<N>.yaml`，每个文件含：

```yaml
name: investment_thesis
version: 1
model_hint: deepseek-chat
temperature: 0.3
max_tokens: 2500
response_schema: InvestmentThesis
system: |
  ...
user: |
  Company: {ticker} ({company_name})
  ...
```

`load_prompt(name, version)` 启动期解析 + 缓存，运行期 0 额外 IO。

### 11.3 三层成本围栏

```
请求进入
  │
  ▼  IP 限流（services/rate_limit.py）
  │   每 IP 24h 滑动窗 N 次（默认 /analyze=3, /recalculate-dcf=30）
  │   超限 → HTTP 429 + Retry-After，零 SEC/LLM 调用
  ▼
  路由处理 → bind_client_ip(ip) 进 contextvar
  │
  ▼  LangGraph 跑各节点；遇到 LLM 调用时 …
  │
  ▼  Per-IP LLM 预算（services/llm/budget.py）
  │   单 IP 24h 累计 spend ≥ AQ_LLM_PER_IP_DAILY_BUDGET_USD
  │   → LLMBudgetExceeded(scope=per_ip) → 节点降级
  ▼
  ▼  全局 LLM 预算
  │   全部 IP 24h 累计 spend ≥ AQ_LLM_DAILY_BUDGET_USD
  │   → LLMBudgetExceeded(scope=global) → 当天剩余所有 LLM 调用全降级
  ▼
  实际 HTTPS 到 LLM provider
```

阈值由 `services/runtime_settings.RuntimeSettings` 管理：env 提供启动默认，admin API 提供运行时覆盖（重启回 env）。

### 11.4 Admin API（`backend/backend/api/admin.py`）

```
Bearer AQ_ADMIN_TOKEN 保护（token 空时整路由 503）
├── GET  /api/admin/settings                看 effective + overrides
├── PATCH /api/admin/settings               动态改预算/限流（SettingsPatch extra=forbid）
├── POST /api/admin/settings/reset          一键回 env
├── GET  /api/admin/usage                   24h 花费、按 task 分组、按 IP top10、限流命中
└── PATCH /api/admin/users/{email}/tier     手动升降级（v0.7 加入）
```

### 11.5 Token 计费日志格式

每次成功 LLM 调用发一条 JSON line（`logger=llm.accounting`）：

```json
{
  "task_tag": "thesis",
  "provider": "primary",
  "model": "deepseek-chat",
  "input_tokens": 2143,
  "output_tokens": 487,
  "estimated_cost_usd": 0.000437,
  "duration_ms": 2174,
  "timestamp": 1714008342.7,
  "client_ip": "203.0.113.42"
}
```

可直接喂给 `jq` / log pipeline 做聚合。

---

## 12. Phase 3 — 5 个 LLM Pro 节点（v0.6.0）

分析管线从 8 节点扩到 12 节点。新增的 5 个节点都是研究密集型 LLM 任务，遵循统一防幻觉链路。

### 12.1 完整管线（12 节点）

```
fetch_sec_data
    ↓
financial_health_scan
    ↓
dynamic_dcf
    ↓
relative_valuation
    ↓
event_sentiment            [LLM #1]
    ↓
event_impact               [LLM #2 + #3]   两步：filter → analysis
    ↓
strategy
    ↓
qualitative_analysis       [LLM #4 + #5, Pro]   并行：MD&A + Risk Factors
    ↓
risk_yoy_diff              [LLM #6, Pro]   今年 vs 去年 10-K
    ↓
moat_analysis              [LLM #7, Pro]   Helmer 7 Powers
    ↓
investment_thesis          [LLM #8, Pro]   综合研报
    ↓
logic_trace
```

单次完整分析 8 次 LLM 调用，DeepSeek 全程 ~$0.01。

### 12.2 5 个新 Pro 节点

| 节点 | 输入 | 输出 schema | 引文核验 |
|------|------|-------------|---------|
| `qualitative_analysis` (MD&A 部分) | 10-K Item 7（前 12K 字符，head+tail） | `MDNAInsight`：tone / forward_guidance / drivers / concerns / notable_quotes | `verify_quotes()` 丢弃幻觉引文 |
| `qualitative_analysis` (Risk Factors 部分) | 10-K Item 1A（前 16K 字符，head only） | `RiskFactorInsight`：8 类风险计数 / Top 5 risks / concentration_risk | `_verify_risk_quote()` 丢弃整条 risk |
| `risk_yoy_diff` | 当年 + 去年 10-K Item 1A（各 12K） | `RiskYoYDiff`：4 桶（new / removed / escalated / de-escalated） | 双源核验：new 验 current；removed 验 prior；escalated/de-escalated 双向都验 |
| `moat_analysis` | 10-K Item 1（前 12K，head+tail） | `MoatInsight`：7 powers 各 0-10 + classification + primary_powers | 不可核验时把 score demote 到 0（保留行结构） |
| `investment_thesis` | 全部上游 state | `InvestmentThesis`：headline + recommendation + bull/bear/risks + action_summary | — |

### 12.3 防幻觉机制（共三层）

1. **System prompt 强约束**：每个 prompt 明令"只能从 USER_CONTENT 边界内提取，禁止使用训练数据知识"。Prompt 文件在 `backend/backend/prompts/`。
2. **Pydantic 模型校验**：`response_model` 强制类型/枚举/长度，校验失败 → `LLMParseError` → 节点降级。
3. **逐字引文核验**（最关键）：所有从源文本抽取的引文都过 `verify_quotes()` —— 必须是源文本的 substring（白空格归一化 + smart-quote 归一化）。
   - MD&A: 假引文丢弃
   - Risk Factors: 整条 risk 丢弃
   - YoY diff: 双源都得过，否则整条 change 丢弃
   - Moat: score 降到 0，rationale 加 `[demoted]` 前缀

### 12.4 10-K 解析（`services/tenk_parser.py`）

提取三节内容，每节用三层正则回退（strict_multi_ws → loose_any_ws → fallback）+ "取最后一次出现"自动避开 ToC：

| 函数 | 节 | 边界 |
|------|---|------|
| `extract_mdna(html)` | Item 7 Management's Discussion and Analysis | → Item 7A 或 Item 8 |
| `extract_risk_factors(html)` | Item 1A Risk Factors | → Item 1B 或 Item 2 |
| `extract_business(html)` | Item 1 Business | → Item 1A |

截断助手：

- `smart_truncate(text, max_chars)`: 头 + 尾 + 中间 `[...truncated...]` 标记。MD&A / Business 用（保留 Overview + Liquidity）。
- `truncate_head(text, max_chars)`: 仅头部。Risk Factors 用（公司按重要性排序，头部即关键）。

### 12.5 SEC 客户端 10-K 多年获取

`SECClient.fetch_10k(cik, n_back=N)`：n_back=0 是最新，n_back=1 是上一年，以此类推。**进程级 6 条 FIFO HTML 缓存**（按 accession_number），同一请求多个节点共享下载。

### 12.6 前端组件

`frontend/src/components/analysis/`：

| 组件 | 内容 |
|------|------|
| `investment-thesis-card.tsx` | Bull/Bear/Risks 三栏 + recommendation 徽章 + confidence |
| `qualitative-insights-card.tsx` | tone 徽章 + forward guidance + 双栏（drivers/concerns）+ verbatim quotes |
| `risk-factors-card.tsx` | 8 类风险徽章条 + Top risks 列表（category 图标 + severity 徽章 + 引文） |
| `risk-yoy-diff-card.tsx` | 4 桶 2x2 网格；escalated/de_escalated 显示 prior↔current 并排引文 |
| `moat-analysis-card.tsx` | 7 power 渐变进度条 + primary badge + verbatim 引文 |
| `pro-locked-card.tsx` | **共享**锁定预览卡片（4 个 Pro `*_locked_card` 都映射到这个，详见 §13.4） |

---

## 13. Phase 2 — 认证 + 订阅分级（v0.7.0）

引入用户身份系统：3 种登录方式 + Postgres 持久化 + JWT 会话 + Pro 节点 tier 门控。

### 13.1 数据 schema

```
users
├── id (PK)
├── email (UNIQUE, INDEX)
├── password_hash (NULL for OAuth-only / magic-link-only users)
├── tier             ← CHECK ('free'|'pro'|'admin')
├── is_active
├── email_verified
├── display_name
└── created_at / updated_at / last_login_at

identity_providers
├── id (PK)
├── user_id (FK→users, ON DELETE CASCADE)
├── kind             ← CHECK ('email_password'|'magic_link'|'google')
├── external_id      ← email for password/magic_link, Google sub for google
├── created_at / last_used_at
├── UNIQUE (user_id, kind)        ← 同一用户同一 kind 至多一行
└── UNIQUE (kind, external_id)    ← 同一 Google sub 不能挂两个用户
```

支持「同一邮箱挂多种登录方式」：用户先用密码注册，再点"用 Google 登录"会把 Google identity 行链接到同一 `users.id`。

### 13.2 三种登录方式 + 同一份 AuthService

```
邮箱密码 ─┐
Magic Link ─┼─→ AuthService.upsert_*_user(...) → User row + IdentityProvider row → JWT cookie
Google OAuth ─┘
```

每种 provider 是 `services/auth/` 下的一个独立模块，外部只通过 `AuthService` 访问，便于后续扩展（GitHub OAuth / Apple Sign-in / SAML 等只需加一个文件 + 一组路由）。

### 13.3 认证流程

#### Email + Password
```
POST /api/auth/email/register {email, password, display_name?}
   → User 创建 (tier=AQ_DEFAULT_USER_TIER, password_hash=bcrypt(...))
   → IdentityProvider(kind='email_password', external_id=email)
   → JWT 写入 aq_session cookie + 返回 body

POST /api/auth/email/login {email, password}
   → bcrypt verify (恒定时间, 防 timing oracle)
   → 同上
```

#### Magic Link（无密码）
```
POST /api/auth/magic-link/send {email}
   → itsdangerous URLSafeTimedSerializer.dumps({email})
   → 发邮件（Resend HTTP API；无 key 时 stderr 打印 + 响应中返 dev_link）
   → 返回 {sent: true}（不暴露用户是否存在，防枚举）

GET (浏览器点邮件链接) /auth/magic-link/verify?token=...
   → 前端调 POST /api/auth/magic-link/verify {token}
   → itsdangerous loads(token, max_age=15min)
   → AuthService.upsert_magic_link_user(email)
       - 不存在 → 创建（email_verified=True，因为邮件可达即证明持有）
       - 存在但未验证 → 翻 email_verified=True
   → 链接 IdentityProvider(kind='magic_link') + JWT cookie
```

#### Google OAuth（authlib OIDC）
```
GET /api/auth/google/start
   → SessionMiddleware 生成 state
   → 302 重定向到 Google authorize endpoint

GET /api/auth/google/callback?code=...&state=...
   → authlib exchange code → access_token + id_token
   → 解出 userinfo（sub, email, name, email_verified）
   → AuthService.upsert_google_user(google_sub, email, ...)
       - 优先按 google_sub 找已链接用户
       - 否则按 email 找现有用户并链接 Google identity
       - 都没有 → 新建 user
   → JWT cookie + 302 → 前端首页
```

### 13.4 Tier 门控

```
api/routes.py /analyze
   ↓ Depends(get_optional_user)              ← 匿名也通过，user=None
   ↓ user_tier = user.tier if user else "free"
   ↓ initial_state["user_tier"] = user_tier
   ↓ LangGraph 跑节点
       │
       ├─ 4 个 Pro 节点（thesis/qualitative/risk_yoy_diff/moat）开头：
       │     if not is_pro_user(state):                     ← _pro_gate.is_pro_user(state)
       │         return emit_lock(...).payload              ← 推一条 *_locked_card ComponentEvent
       │
       └─ 7 个 Free 节点：照常跑
```

`_pro_gate.emit_lock(...)` 推送的 `ComponentEvent` 带 `feature_label` / `entity_name` / `preview_*`，前端 `pro-locked-card.tsx` 渲染锁定预览 + Upgrade CTA。

4 个 Pro 节点对应的 locked component_type：
- `investment_thesis_locked_card`
- `qualitative_locked_card`
- `risk_yoy_diff_locked_card`
- `moat_locked_card`

四者全部映射到同一个 React 组件 `pro-locked-card.tsx`，由后端注入的 `feature_label` 驱动文案差异。

### 13.5 会话凭证

JWT (HS256) 同时通过两条路下发：

| 渠道 | 适用 |
|------|------|
| `aq_session` HTTP-only cookie（`SameSite=Lax`） | 浏览器 SPA |
| 响应 body `{token}` | API 客户端（可放 `Authorization: Bearer`） |

`get_optional_user` / `get_current_user` 两个 FastAPI dep 都先看 cookie 再看 header。

### 13.6 前端

```
src/context/auth-context.tsx       ← <AuthProvider> + useAuth()
                                     status ∈ {loading, authenticated, anonymous}
                                     isPro 派生属性
src/lib/auth-api.ts                ← 类型化 fetch wrappers
src/app/auth/login/page.tsx        ← 三 tab：Password / Magic link / Google
src/app/auth/register/page.tsx     ← 邮箱密码注册
src/app/auth/magic-link/verify/page.tsx ← 接 ?token= → 调 verify → 跳首页
```

`<AuthProvider>` 在 root layout 包裹 `<HistoryProvider>` 外层，全站可用 `useAuth()`。

### 13.7 手工 Pro 升级（pre-Stripe）

```bash
# 升级
curl -X PATCH \
  -H "Authorization: Bearer $AQ_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier":"pro"}' \
  http://localhost:8000/api/admin/users/foo@bar.com/tier

# 或：
make promote EMAIL=foo@bar.com
```

Stripe 集成留待后续；当前 admin 接口长期保留作为运营覆盖手段。

---

## 14. 完整目录结构（截至 v0.7.0）

```
alpha/
├── docker-compose.yml              # Postgres for local dev
├── Makefile                         # 一键 dev/test/migrate/promote
├── scripts/dev-setup.sh             # 一次性 bootstrap
├── DEVELOPMENT.md                   # 共同开发者上手指南
├── ARCHITECTURE.md                  # ← 本文件
├── CHANGELOG.md
├── MVP-GAP.html
│
├── backend/
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                   # Async migration runner
│   │   └── versions/
│   │       └── 20260425_0001_init_users.py
│   ├── pyproject.toml
│   ├── .env / .env.example
│   ├── backend/
│   │   ├── main.py                  # + SessionMiddleware, auth_router, DB lifespan
│   │   ├── config.py                # 全部 AQ_* env 字段
│   │   ├── api/
│   │   │   ├── routes.py            # /analyze + /recalculate-dcf (含 IP 限流 + tier 注入)
│   │   │   ├── admin.py             # /api/admin/* (settings + usage + users/{email}/tier)
│   │   │   ├── auth.py              # /api/auth/* (8 路由 covering 3 providers)
│   │   │   └── dependencies.py
│   │   ├── agents/
│   │   │   ├── value_analyst.py     # 12 节点 StateGraph
│   │   │   └── nodes/
│   │   │       ├── _pro_gate.py     # 共享 tier 门控 helper
│   │   │       ├── financial_health.py
│   │   │       ├── dcf_model.py
│   │   │       ├── relative_valuation.py + relative_valuation_math.py
│   │   │       ├── event_sentiment.py + event_sentiment_math.py
│   │   │       ├── event_impact.py + event_impact_math.py
│   │   │       ├── strategy.py
│   │   │       ├── qualitative_analysis.py    # MD&A + Risk Factors 并行
│   │   │       ├── risk_yoy_diff.py           # 双源核验
│   │   │       ├── moat_analysis.py           # Helmer 7 Powers
│   │   │       ├── investment_thesis.py       # 综合研报
│   │   │       └── logic_trace.py
│   │   ├── prompts/
│   │   │   ├── __init__.py          # YAML loader + cache
│   │   │   ├── sentiment_v1.yaml
│   │   │   ├── event_filter_v1.yaml
│   │   │   ├── event_analysis_v1.yaml
│   │   │   ├── mdna_analysis_v1.yaml
│   │   │   ├── risk_factors_v1.yaml
│   │   │   ├── risk_yoy_diff_v1.yaml
│   │   │   ├── moat_analysis_v1.yaml
│   │   │   └── investment_thesis_v1.yaml
│   │   ├── services/
│   │   │   ├── ticker_resolver.py
│   │   │   ├── sec_client.py        # + fetch_10k(n_back) + 6条FIFO HTML缓存
│   │   │   ├── sec_agent.py
│   │   │   ├── tenk_parser.py       # extract_mdna / extract_risk_factors / extract_business
│   │   │   ├── market_data.py
│   │   │   ├── finnhub_client.py
│   │   │   ├── llm_sentiment.py     # 改瘦身 wrapper，走 LLMClient
│   │   │   ├── db.py                # Async SQLAlchemy engine
│   │   │   ├── runtime_settings.py  # env defaults + admin overrides
│   │   │   ├── request_context.py   # contextvars for client IP
│   │   │   ├── rate_limit.py        # IP rate limiter
│   │   │   ├── llm/
│   │   │   │   ├── client.py        # LLMClient
│   │   │   │   ├── providers.py     # OpenAICompatibleProvider
│   │   │   │   ├── sanitize.py
│   │   │   │   ├── accounting.py    # AccountingStore
│   │   │   │   ├── budget.py        # BudgetGate
│   │   │   │   └── errors.py
│   │   │   └── auth/
│   │   │       ├── models.py         # User + IdentityProvider ORM
│   │   │       ├── service.py        # AuthService
│   │   │       ├── passwords.py      # bcrypt
│   │   │       ├── tokens.py         # JWT
│   │   │       ├── magic_link.py     # itsdangerous + Resend
│   │   │       ├── google_oauth.py   # authlib OIDC
│   │   │       └── dependencies.py   # get_current_user / require_pro / ...
│   │   └── models/
│   │       ├── agent_state.py       # + user_tier + qualitative_result + risk_yoy_diff_result + moat_result + investment_thesis_result
│   │       ├── events.py
│   │       ├── financial.py
│   │       └── sec.py
│   └── tests/
│
└── frontend/
    └── src/
        ├── app/
        │   ├── layout.tsx           # 包了 AuthProvider
        │   ├── page.tsx
        │   ├── analyze/[ticker]/page.tsx
        │   └── auth/                # ← 新增（v0.7）
        │       ├── login/page.tsx           # 三 tab
        │       ├── register/page.tsx
        │       └── magic-link/verify/page.tsx
        ├── context/
        │   ├── history-context.tsx
        │   └── auth-context.tsx     # ← 新增
        ├── hooks/
        │   ├── use-sse.ts
        │   └── use-analysis-stream.ts
        ├── lib/
        │   ├── types.ts             # + Tier / AuthUser / AuthSessionResponse
        │   ├── constants.ts
        │   ├── auth-api.ts          # ← 新增
        │   └── utils.ts
        └── components/
            ├── component-registry.ts  # 18 entries (12 free + 4 Pro + 4 locked aliases）
            └── analysis/
                ├── (12 个 free 卡片)
                ├── investment-thesis-card.tsx     # 4 Pro 卡片
                ├── qualitative-insights-card.tsx
                ├── risk-factors-card.tsx
                ├── risk-yoy-diff-card.tsx
                ├── moat-analysis-card.tsx
                └── pro-locked-card.tsx            # 共享锁定预览
```

> **注**: 未设置 `AQ_FMP_API_KEY` 时, 相对估值和策略分析自动跳过。未设置 `AQ_FINNHUB_API_KEY` 时, 消息面情绪节点自动跳过。其余功能正常。在 `.env` 中设置即可启用, config.py 会自动从项目根目录向上查找该文件。
