# AlphaQuant - System Architecture & Workflow

## 文档地图

> 文档体系分三层：本文档 (系统全景) → `docs/nodes/` (节点详情) → `docs/decisions/` (架构决策)。
> 详细的目录结构见下方 Section 2。

**快速定位**:

| 你想知道... | 去哪里 |
|------------|--------|
| 系统整体怎么跑的 | 继续读本文档 |
| 某个节点的具体实现 | `docs/nodes/{编号}-{名称}.md` |
| 某个设计为什么这样做 | `docs/decisions/{编号}-{主题}.md` |
| 数据结构定义 | 代码是真相源: `backend/models/agent_state.py`, `events.py`, `financial.py` |
| API 端点格式 | 本文档 Section 7: API Contract |
| 版本变更历史 | `CHANGELOG.md` |
| MVP 上线差距 | `MVP-GAP.md` |
| AI Agent 开发指南 | `frontend/CLAUDE.md` |

---

## 1. System Overview

AlphaQuant is a white-box AI investment research system. It fetches raw SEC EDGAR filings, runs multi-step value analysis through a LangGraph state machine, and streams the reasoning process and results as Generative UI components to a React frontend in real-time via Server-Sent Events (SSE).

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js 16)                       │
│                                                                     │
│  ┌──────────────┐     ┌─────────────┐     ┌──────────────────────┐ │
│  │  Home Page    │────>│  useSSE     │────>│  AppShell            │ │
│  │  (Ticker Input)     │  (EventSource)    │  ┌──────────┐┌─────┐ │ │
│  └──────────────┘     └──────┬──────┘     │  │Conversa- ││Analy-│ │ │
│                              │             │  │tionPanel ││sisCa-│ │ │
│                              │             │  │(思考链)  ││nvas  │ │ │
│                              │             │  └──────────┘└──┬──┘ │ │
│                              │             └────────────────┼────┘ │
│                              │                              │      │
│                    SSE Stream│              Component Registry      │
│                    (实时推送) │              (lazy load 12 组件)    │
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
alphaquant/
├── ARCHITECTURE.md                              # 系统架构全景 (你在这里)
├── CHANGELOG.md                                 # 版本变更记录
├── MVP-GAP.md                                   # MVP 差距分析与路线图
│
├── docs/
│   ├── nodes/                                   # 节点详细文档 (8 个)
│   │   ├── 01-fetch-sec-data.md                 #   Node 1: SEC EDGAR 数据获取
│   │   ├── 02-financial-health.md               #   Node 2: 财务健康扫描
│   │   ├── 03-dcf-model.md                      #   Node 3: DCF 估值建模
│   │   ├── 04-relative-valuation.md             #   Node 4: 相对估值
│   │   ├── 05-event-sentiment.md                #   Node 5: 消息面情绪分析
│   │   ├── 06-event-impact.md                   #   Node 6: 事件影响 + DCF 重算
│   │   ├── 07-strategy.md                       #   Node 7: 买入策略
│   │   └── 08-logic-trace.md                    #   Node 8: SEC 数据溯源
│   └── decisions/                               # 架构决策记录 ADR (5 个)
│       ├── 001-xbrl-tag-fallback.md             #   XBRL 标签回退策略
│       ├── 002-two-stage-dcf.md                 #   两阶段 DCF 设计
│       ├── 003-stream-writer-over-astream.md    #   StreamWriter 选择
│       ├── 004-separate-recalc-endpoint.md      #   独立重算端点
│       └── 005-fmp-stable-api.md                #   FMP /stable/ API 选择
│
├── backend/
│   ├── pyproject.toml                           # Python 依赖定义
│   ├── backend/
│   │   ├── main.py                              # FastAPI 入口 + lifespan 管理
│   │   ├── config.py                            # pydantic-settings 配置 (自动发现 .env)
│   │   ├── models/
│   │   │   ├── sec.py                           # SEC EDGAR 原始响应模型
│   │   │   ├── financial.py                     # 归一化后的财务指标模型
│   │   │   ├── agent_state.py                   # LangGraph TypedDict 状态
│   │   │   └── events.py                        # SSE 事件模型 (Generative UI 协议)
│   │   ├── services/
│   │   │   ├── ticker_resolver.py               # Ticker → CIK 映射
│   │   │   ├── sec_client.py                    # EDGAR HTTP 客户端 (httpx, 10 req/s)
│   │   │   ├── sec_agent.py                     # XBRL 归一化层 (核心领域逻辑)
│   │   │   ├── market_data.py                   # FMP 市场行情客户端 (httpx)
│   │   │   ├── finnhub_client.py                # Finnhub 新闻/内部人情绪客户端
│   │   │   └── llm_sentiment.py                 # DeepSeek LLM 新闻情绪分析
│   │   ├── agents/
│   │   │   ├── value_analyst.py                 # LangGraph StateGraph 编排
│   │   │   └── nodes/
│   │   │       ├── financial_health.py          # 节点 2: 财务健康扫描
│   │   │       ├── dcf_model.py                 # 节点 3: 动态 DCF 建模 + compute_dcf()
│   │   │       ├── relative_valuation.py        # 节点 4: 相对估值 (主节点, 含 I/O)
│   │   │       ├── relative_valuation_math.py   # 节点 4: 纯计算函数 (无 I/O)
│   │   │       ├── event_sentiment.py           # 节点 5: 消息面情绪分析 (主节点)
│   │   │       ├── event_sentiment_math.py      # 节点 5: 纯计算函数 (过滤/评分/标签)
│   │   │       ├── event_impact.py              # 节点 6: 事件影响 (两步 LLM + DCF 重算)
│   │   │       ├── event_impact_math.py         # 节点 6: 纯计算函数 (参数注册表/调整/重算)
│   │   │       ├── industry_mapping.py          # 行业映射工具 (SIC → 行业)
│   │   │       ├── strategy.py                  # 节点 7: 安全边际 & 买入策略
│   │   │       └── logic_trace.py               # 节点 8: SEC 数据溯源
│   │   ├── utils/
│   │   │   └── __init__.py                      # 通用工具函数
│   │   └── api/
│   │       ├── routes.py                        # SSE + 重算端点
│   │       └── dependencies.py                  # 内存缓存 (DCF 重算用)
│   └── tests/
│       └── agents/nodes/
│           ├── test_event_impact_math.py        # 事件影响计算单元测试
│           ├── test_event_sentiment_math.py     # 情绪计算单元测试
│           ├── test_industry_mapping.py         # 行业映射单元测试
│           └── test_relative_valuation_math.py  # 相对估值计算单元测试
│
└── frontend/
    ├── CLAUDE.md                               # AI Agent 开发指南 (EN)
    └── src/
        ├── app/
        │   ├── layout.tsx                       # 根布局
        │   ├── page.tsx                         # 首页 (Ticker 输入)
        │   └── analyze/[ticker]/page.tsx        # 分析页 (动态路由)
        ├── hooks/
        │   ├── use-sse.ts                       # 底层 EventSource 封装
        │   └── use-analysis-stream.ts           # 高层分析流 Hook
        ├── context/
        │   └── history-context.tsx              # 分析历史 Context
        ├── components/
        │   ├── component-registry.ts            # 类型 → React 组件映射
        │   ├── analysis-canvas.tsx              # 分析画布 (动态组件挂载器)
        │   ├── conversation-panel.tsx           # Agent 推理面板 (打字机效果)
        │   ├── empty-state.tsx                  # 空状态占位
        │   ├── layout/
        │   │   ├── app-shell.tsx                # 应用外壳 (路由 + 布局)
        │   │   └── sidebar.tsx                  # 侧边栏 (历史/导航)
        │   ├── analysis/
        │   │   ├── chart-primitives.tsx         # 图表基础组件 (Recharts 封装)
        │   │   ├── metric-table.tsx             # 关键指标表
        │   │   ├── revenue-chart.tsx            # 营收柱状图
        │   │   ├── fcf-chart.tsx                # FCF 历史+预测图
        │   │   ├── financial-health-card.tsx    # 财务健康卡片
        │   │   ├── dcf-result-card.tsx          # DCF 估值结果
        │   │   ├── valuation-gauge.tsx          # 估值仪表
        │   │   ├── assumption-slider.tsx        # 假设参数滑块
        │   │   ├── relative-valuation-card.tsx  # 相对估值卡片 (乘数+百分位+同业)
        │   │   ├── sentiment-card.tsx           # 消息面情绪卡片 (仪表+新闻+内部人)
        │   │   ├── event-impact-card.tsx        # 事件影响卡片 (参数对比+DCF重算)
        │   │   ├── strategy-dashboard.tsx       # 估值热力仪表盘 (买入策略)
        │   │   └── source-table.tsx             # SEC 数据溯源表
        │   └── ui/                              # shadcn/ui 基础组件
        │       ├── badge.tsx
        │       ├── button.tsx
        │       ├── card.tsx
        │       ├── input.tsx
        │       ├── separator.tsx
        │       ├── skeleton.tsx
        │       ├── slider.tsx
        │       ├── table.tsx
        │       └── tabs.tsx
        └── lib/
            ├── types.ts                         # TypeScript 类型定义
            ├── constants.ts                     # API 地址常量
            └── utils.ts                         # 工具函数
```

> **注**: Node 1 (`fetch_sec_data`) 的逻辑由 `sec_agent.py` (服务层) + `value_analyst.py` (编排层) 共同完成，无独立节点文件。`industry_mapping.py` 为 Node 4 (相对估值) 提供行业分类支持。

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
    │   └── AppShell.setTicker("NVDA") — 状态更新, 无路由跳转
    │
    └── 直接访问 /analyze/NVDA 时:
        ├── app/analyze/[ticker]/page.tsx 渲染
        ├── const { ticker } = use(params)  // Next.js 16: params 是 Promise
        └── <AppShell initialTicker="NVDA" />
```

### Phase 2: SSE Connection (Frontend → Backend)

```
AppShell 挂载
    │
    ├── useAnalysisStream("NVDA")
    │   └── useSSE({ url: "http://localhost:8000/api/analyze/NVDA" })
    │       └── new EventSource(url)
    │           ├── 注册监听: agent_thinking, component, step_complete,
    │           │              analysis_complete, error
    │           └── status: "connecting" → "connected"
    │
    └── 渲染初始 UI
        ├── ConversationPanel: "Initializing analysis..." (动画)
        └── AnalysisCanvas: 空 (等待组件)
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
    │       relative_valuation_result: None,   # 节点4填充 (相对估值)
    │       event_sentiment_result: None,      # 节点5填充 (消息面情绪)
    │       event_impact_result: None,         # 节点6填充 (事件影响+DCF重算)
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

#### 节点总览

每个节点的详细文档 (逻辑流程、输入/输出、关键假设、失败模式) 请参阅 `docs/nodes/`。

| # | 节点 | 职责 | State 输出 | 前端组件 | 详细文档 |
|---|------|------|------------|----------|----------|
| 1 | `fetch_sec_data` | SEC EDGAR 数据获取 + XBRL 归一化 | `financials` | MetricTable | [01-fetch-sec-data.md](docs/nodes/01-fetch-sec-data.md) |
| 2 | `financial_health_scan` | 财务健康扫描 (ICR, D/E, 利润率, CAGR) | `health_metrics`, `health_assessment` | FinancialHealthCard, RevenueChart | [02-financial-health.md](docs/nodes/02-financial-health.md) |
| 3 | `dynamic_dcf` | 两阶段 DCF 估值建模 | `dcf_result` | FCFChart, DCFResultCard, ValuationGauge, AssumptionSlider | [03-dcf-model.md](docs/nodes/03-dcf-model.md) |
| 4 | `relative_valuation` | 相对估值 (当前乘数 + 历史百分位 + 同业对比) | `relative_valuation_result` | RelativeValuationCard | [04-relative-valuation.md](docs/nodes/04-relative-valuation.md) |
| 5 | `event_sentiment` | 消息面情绪分析 (新闻 + 内部人 + LLM) | `event_sentiment_result` | SentimentCard | [05-event-sentiment.md](docs/nodes/05-event-sentiment.md) |
| 6 | `event_impact` | 事件影响分析 + DCF 参数调整重算 | `event_impact_result` | EventImpactCard | [06-event-impact.md](docs/nodes/06-event-impact.md) |
| 7 | `strategy` | 安全边际 & 买入策略 (MoS + P/E 分位数 + 情绪修正) | `strategy_result` | StrategyDashboard | [07-strategy.md](docs/nodes/07-strategy.md) |
| 8 | `logic_trace` | 数据溯源 (14 指标 × 5 年 → SEC 原始链接) | `source_map`, `verdict` | SourceTable | [08-logic-trace.md](docs/nodes/08-logic-trace.md) |

**节点间数据流**:
```
fetch_sec_data ──financials──> financial_health ──(隐式)──> dynamic_dcf
                                                              │
                              relative_valuation <──financials──┘
                                      │
                              event_sentiment <──financials──┘
                                      │
                              event_impact <──sentiment + dcf──┘
                                      │
                              strategy <──dcf + rel_val + sentiment + impact──┘
                                      │
                              logic_trace <──all results──┘
```

### Phase 4: Frontend Rendering (全程实时)

```
SSE 事件流时序 (共约 25 个事件):
    │
    │  ┌─ ConversationPanel (左栏 2/5) ──────┐  ┌─ AnalysisCanvas (右栏 3/5) ─────────┐
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
    ├── app-shell.tsx: handleRecalculate({
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
    └── app-shell.tsx: setUpdatedComponents(...)
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
AppShell
    ├── ConversationPanel ← thinkingMessages[]
    │   └── ReasoningAccordion (可折叠推理段落, 打字机效果)
    │       └── node 标签: 按 node 名称分组显示
    │
    └── AnalysisCanvas ← components[]
        └── 遍历 ComponentInstruction[]
            └── getComponent(type) → lazy React component
                └── <Component {...props} /> 渲染
```

---

## 5. Key Data Models

> **真相源**: 以下数据结构的权威定义在代码中。文档是对代码的可读摘要，如有冲突以代码为准。

| 模型 | 代码位置 | 说明 |
|------|----------|------|
| `SECCompanyFacts` | `backend/models/sec.py` | SEC EDGAR 原始响应 (XBRL) |
| `CompanyFinancials` | `backend/models/financial.py` | 16 个归一化财务指标时间序列 |
| `AnalysisState` | `backend/models/agent_state.py` | LangGraph 共享状态 (TypedDict) |
| `SSEEvent` | `backend/models/events.py` | 5 种 SSE 事件类型 (Pydantic) |

### AnalysisState 概览

```
AnalysisState (TypedDict)
├── ticker: str                         # 输入
├── financials: CompanyFinancials|None   # Node 1
├── fetch_errors: list[str]             # Node 1
├── health_metrics: dict | None         # Node 2
├── health_assessment: str | None       # Node 2
├── dcf_result: dict | None             # Node 3
├── relative_valuation_result: dict|None # Node 4
├── event_sentiment_result: dict|None   # Node 5
├── event_impact_result: dict|None      # Node 6
├── strategy_result: dict | None        # Node 7
├── source_map: dict | None             # Node 8
├── reasoning_steps: list[str]          # 追加模式
└── verdict: str | None                 # Node 8
```

---

## 6. Critical Design Decisions

关键架构决策的详细分析（背景、选项、决策、后果）请参阅 `docs/decisions/`：

| ADR | 决策 | 核心权衡 |
|-----|------|----------|
| [001](docs/decisions/001-xbrl-tag-fallback.md) | XBRL 标签回退: 选 latest_year 最大的 | 适应性 vs 口径差异风险 |
| [002](docs/decisions/002-two-stage-dcf.md) | 两阶段 DCF (非三阶段) | 简洁性 vs 参数精度 |
| [003](docs/decisions/003-stream-writer-over-astream.md) | StreamWriter (非 astream_events) | 事件可控性 vs token 级实时性 |
| [004](docs/decisions/004-separate-recalc-endpoint.md) | 独立重算端点 (非重跑全图) | 响应速度 vs 数据新鲜度 |
| [005](docs/decisions/005-fmp-stable-api.md) | FMP /stable/ API (非 yfinance) | 官方支持 vs 社区生态 |

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

核心原则：**优雅降级**。除 `fetch_sec_data` 失败（Ticker 不存在/SEC API 不可用）会终止分析外，所有其他节点的失败都不阻塞后续流程。

详细错误处理表见各节点文档 (`docs/nodes/`) 的"失败模式与降级"章节。

关键降级路径：
- 无 `AQ_FMP_API_KEY` → relative_valuation (price_available=false) + strategy 跳过
- 无 `AQ_FINNHUB_API_KEY` → event_sentiment + event_impact 跳过
- 无 `AQ_LLM_API_KEY` → event_impact 跳过, LLM 情绪降级为关键词分析
- 节点异常 → `ErrorEvent(recoverable=True)` → logic_trace 仍执行

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
