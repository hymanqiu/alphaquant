# AlphaQuant - System Architecture & Workflow

## 文档地图

> 文档体系分三层：本文档 (系统全景) → `docs/nodes/` (节点详情) → `docs/decisions/` (架构决策)。
> 详细的目录结构见下方 Section 2。

**快速定位**:

| 你想知道... | 去哪里 |
|------------|--------|
| 系统整体怎么跑的 | 继续读本文档 |
| 某个节点的具体实现 | `docs/nodes/{01-12}-*.md`（12 个节点详情） |
| 某个设计为什么这样做 | `docs/decisions/{001-009}-*.md`（9 条 ADR） |
| Phase 1/2/3（v0.5+）做了什么 | 本文档 Section 10 + 对应 ADR |
| 数据结构定义 | 代码是真相源: `backend/models/agent_state.py`, `events.py`, `financial.py` |
| API 端点格式 | 本文档 Section 7: API Contract |
| 版本变更历史 | `CHANGELOG.md` |
| MVP 上线差距 | `MVP-GAP.md` |
| 新人上手 / 本地起服务 | `DEVELOPMENT.md` + `make help` |
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
│   ├── nodes/                                   # 节点详细文档 (12 个)
│   │   ├── 01-fetch-sec-data.md                 #   Node 1: SEC EDGAR 数据获取
│   │   ├── 02-financial-health.md               #   Node 2: 财务健康扫描
│   │   ├── 03-dcf-model.md                      #   Node 3: DCF 估值建模
│   │   ├── 04-relative-valuation.md             #   Node 4: 相对估值
│   │   ├── 05-event-sentiment.md                #   Node 5: 消息面情绪分析
│   │   ├── 06-event-impact.md                   #   Node 6: 事件影响 + DCF 重算
│   │   ├── 07-strategy.md                       #   Node 7: 买入策略
│   │   ├── 08-logic-trace.md                    #   Node 8: SEC 数据溯源
│   │   ├── 09-qualitative-analysis.md           # 🆕 Node 9: 10-K MD&A + Risk Factors (Pro)
│   │   ├── 10-risk-yoy-diff.md                  # 🆕 Node 10: 10-K Risk YoY 对比 (Pro)
│   │   ├── 11-moat-analysis.md                  # 🆕 Node 11: 7 Powers 护城河评分 (Pro)
│   │   └── 12-investment-thesis.md              # 🆕 Node 12: 综合投资论点 (Pro)
│   └── decisions/                               # 架构决策记录 ADR (9 个)
│       ├── 001-xbrl-tag-fallback.md             #   XBRL 标签回退策略
│       ├── 002-two-stage-dcf.md                 #   两阶段 DCF 设计
│       ├── 003-stream-writer-over-astream.md    #   StreamWriter 选择
│       ├── 004-separate-recalc-endpoint.md      #   独立重算端点
│       ├── 005-fmp-stable-api.md                #   FMP /stable/ API 选择
│       ├── 006-unified-llm-client.md            # 🆕 LLM 单一调用入口
│       ├── 007-three-layer-cost-guardrails.md   # 🆕 三层成本围栏
│       ├── 008-pluggable-auth-providers.md      # 🆕 可插拔认证模块
│       └── 009-tier-gating-strategy.md          # 🆕 节点级 tier 门控
│
├── backend/                                     # 下方仅展示 v0.4 之前的核心结构;
│   │                                            # v0.5/0.6/0.7 新增的 services/llm/, services/auth/,
│   │                                            # prompts/, alembic/, 4 个 Pro nodes 等见 §10 完整目录树
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


---

## 10. Beyond v0.4 — Phase 1 / 2 / 3 总览

> v0.5 — v0.7 引入了 LLM 基础设施、5 个 Pro 分析节点、认证 + 订阅分级。**详细实现细节** 见 `docs/nodes/` 和 `docs/decisions/`；本节只提供高层导览。

### Phase 1 — LLM 基础设施 + 成本围栏（v0.5.0）

把分散的 LLM 调用收编到 `services/llm/` 统一入口，叠加三层成本围栏。

| 主题 | 详细文档 |
|------|---------|
| LLM 单一调用入口（client / providers / sanitize / accounting / errors） | [ADR 006: unified-llm-client](decisions/006-unified-llm-client.md) |
| 三层成本围栏（IP 限流 + per-IP 预算 + 全局预算） + admin 热改阈值 | [ADR 007: three-layer-cost-guardrails](decisions/007-three-layer-cost-guardrails.md) |
| Prompt YAML 库（`backend/prompts/<name>_v<N>.yaml`） | 在 ADR 006 中 |

### Phase 3 — 5 个 LLM Pro 节点（v0.6.0）

分析管线从 8 节点扩到 12 节点。Pro 节点统一遵循「LLM 输出 → Pydantic 校验 → 逐字引文核验」防幻觉链路。

| 节点 | 输入 | 详细文档 |
|------|------|---------|
| `qualitative_analysis` 🔒 | 10-K MD&A + Risk Factors（并行） | [Node 09](nodes/09-qualitative-analysis.md) |
| `risk_yoy_diff` 🔒 | 当年 + 上一年 10-K Risk Factors | [Node 10](nodes/10-risk-yoy-diff.md) |
| `moat_analysis` 🔒 | 10-K Item 1 Business | [Node 11](nodes/11-moat-analysis.md) |
| `investment_thesis` 🔒 | 全部上游 state | [Node 12](nodes/12-investment-thesis.md) |

> 🔒 = Pro-only（详见 [ADR 009: tier-gating-strategy](decisions/009-tier-gating-strategy.md)）。

### Phase 2 — 认证 + 订阅分级（v0.7.0）

引入用户身份系统（3 种登录方式 → 同一份 User row）+ Pro 节点 tier 门控。

| 主题 | 详细文档 |
|------|---------|
| 三 provider 模块化抽象（email/password + Magic link + Google OAuth） | [ADR 008: pluggable-auth-providers](decisions/008-pluggable-auth-providers.md) |
| Pro 节点 tier 门控（节点入口 short-circuit + 锁定预览卡） | [ADR 009: tier-gating-strategy](decisions/009-tier-gating-strategy.md) |

### 完整管线（12 节点）

```
fetch_sec_data → financial_health_scan → dynamic_dcf → relative_valuation
              → event_sentiment [LLM]  → event_impact [2× LLM]
              → strategy
              → qualitative_analysis [2× LLM, Pro]   ← MD&A + Risk Factors 并行
              → risk_yoy_diff        [LLM, Pro]      ← 双源核验
              → moat_analysis        [LLM, Pro]      ← 7 Powers
              → investment_thesis    [LLM, Pro]      ← 综合研报
              → logic_trace
```

Free 用户跑 7 个 free 节点 + 4 个 Pro 节点 emit 锁定预览卡（0 LLM 调用）；Pro 用户跑全部 12 节点。

### 完整目录结构（v0.7 后）

```
alpha/
├── docker-compose.yml              # Local Postgres
├── Makefile                         # 一键 dev/test/migrate/promote
├── scripts/dev-setup.sh             # 一次性 bootstrap
├── DEVELOPMENT.md                   # 共同开发者上手指南
├── ARCHITECTURE.md                  # ← 本文件（系统全景）
├── CHANGELOG.md
├── MVP-GAP.md / MVP-GAP.html
│
├── docs/
│   ├── nodes/                       # 节点详细文档（12 个）
│   │   ├── 01-fetch-sec-data.md
│   │   ├── 02-financial-health.md
│   │   ├── 03-dcf-model.md
│   │   ├── 04-relative-valuation.md
│   │   ├── 05-event-sentiment.md
│   │   ├── 06-event-impact.md
│   │   ├── 07-strategy.md
│   │   ├── 08-logic-trace.md
│   │   ├── 09-qualitative-analysis.md   # 🆕 v0.6
│   │   ├── 10-risk-yoy-diff.md          # 🆕 v0.6
│   │   ├── 11-moat-analysis.md          # 🆕 v0.6
│   │   └── 12-investment-thesis.md      # 🆕 v0.6
│   └── decisions/                   # ADR（架构决策记录）
│       ├── 001-xbrl-tag-fallback.md
│       ├── 002-two-stage-dcf.md
│       ├── 003-stream-writer-over-astream.md
│       ├── 004-separate-recalc-endpoint.md
│       ├── 005-fmp-stable-api.md
│       ├── 006-unified-llm-client.md           # 🆕 v0.5
│       ├── 007-three-layer-cost-guardrails.md  # 🆕 v0.5
│       ├── 008-pluggable-auth-providers.md     # 🆕 v0.7
│       └── 009-tier-gating-strategy.md         # 🆕 v0.7
│
├── backend/
│   ├── alembic.ini + alembic/                  # DB migrations (v0.7)
│   ├── pyproject.toml + .env.example
│   └── backend/
│       ├── main.py + config.py
│       ├── api/{routes, admin, auth, dependencies}.py    # admin/auth 是 v0.5/v0.7 新增
│       ├── agents/
│       │   ├── value_analyst.py                          # 12 节点 graph
│       │   └── nodes/
│       │       ├── (8 个原节点)
│       │       ├── _pro_gate.py                          # 🆕 v0.7 tier 门控 helper
│       │       ├── qualitative_analysis.py               # 🆕 v0.6
│       │       ├── risk_yoy_diff.py                      # 🆕 v0.6
│       │       ├── moat_analysis.py                      # 🆕 v0.6
│       │       └── investment_thesis.py                  # 🆕 v0.6
│       ├── prompts/                                       # 🆕 v0.5 YAML library
│       │   └── {sentiment, event_filter, event_analysis,
│       │       mdna_analysis, risk_factors, risk_yoy_diff,
│       │       moat_analysis, investment_thesis}_v1.yaml
│       ├── services/
│       │   ├── (原有 sec / market_data / finnhub / ticker_resolver)
│       │   ├── tenk_parser.py                            # 🆕 v0.6 10-K HTML 解析
│       │   ├── db.py + runtime_settings.py + request_context.py + rate_limit.py
│       │   ├── llm/                                       # 🆕 v0.5 unified LLM
│       │   │   └── {client, providers, sanitize, accounting, budget, errors}.py
│       │   └── auth/                                      # 🆕 v0.7 auth 模块
│       │       └── {models, service, passwords, tokens, magic_link, google_oauth, dependencies}.py
│       └── models/
│           └── agent_state.py                            # + user_tier + 4 个 Pro result fields
│
└── frontend/
    └── src/
        ├── app/
        │   ├── analyze/[ticker]/page.tsx
        │   └── auth/                                     # 🆕 v0.7
        │       ├── login/page.tsx                        #   3 tab: password / magic / google
        │       ├── register/page.tsx
        │       └── magic-link/verify/page.tsx
        ├── context/
        │   ├── history-context.tsx
        │   └── auth-context.tsx                          # 🆕 v0.7
        ├── hooks/{use-sse, use-analysis-stream}.ts
        ├── lib/
        │   ├── auth-api.ts                               # 🆕 v0.7
        │   ├── types.ts (+ Tier / AuthUser)
        │   └── ...
        └── components/
            ├── component-registry.ts                     # 18 entries
            └── analysis/
                ├── (12 个 free 卡片)
                ├── investment-thesis-card.tsx            # 4 Pro 卡片 (v0.6)
                ├── qualitative-insights-card.tsx
                ├── risk-factors-card.tsx
                ├── risk-yoy-diff-card.tsx
                ├── moat-analysis-card.tsx
                └── pro-locked-card.tsx                   # 共享锁定预览 (v0.7)
```

> **注**: 未设置 `AQ_FMP_API_KEY` 时, 相对估值和策略分析自动跳过。未设置 `AQ_FINNHUB_API_KEY` 时, 消息面情绪节点自动跳过。未设置 `AQ_LLM_API_KEY` 时, 所有 LLM 节点（含 5 个 Pro 节点）跳过。未设置 `AQ_DATABASE_URL` 时, auth 整套禁用，所有用户被视为 anonymous（free tier）。在 `.env` 中按需启用即可。

---

## 15. UI Phase 1 — Verdict-First 重构（v0.8.0）

原右侧 canvas 把 19 张卡片纵向堆叠在 4000-6000px 长的列里。本次重构把它替换为：

```
┌─────────────────────────────────────────────────────┐
│ Verdict Hero (sticky)                                │
│  AAPL · Apple Inc.            $189.50 market         │
│  [BUY pill] [+18% MoS] [72% High conf] [3 high ⚠]   │
│  "20% discount to intrinsic; services growth slows"  │
│  Buy < $185 · IV $215 · Upside +14%                  │
├─────────────────────────────────────────────────────┤
│ [Verdict 5][Valuation 8 ●][Strategy 2][Risks 3⚠][Sources 1] │
├─────────────────────────────────────────────────────┤
│  <当前 tab 的卡片，内部独立滚动>                          │
└─────────────────────────────────────────────────────┘
```

### 信息架构

| Tab | 包含组件 | 角色 |
|---|---|---|
| Verdict | `investment_thesis_card` (+ pro-locked) · `qualitative_insights_card` (+ pro-locked) · `strategy_dashboard` | 答案 + 推荐 + 入场区间 |
| Valuation | `dcf_result_card` · `valuation_gauge` · `assumption_slider` · `fcf_chart` · `revenue_chart` · `relative_valuation_card` · `metric_table` · `financial_health_card` | 估值数字（最重 tab） |
| Strategy | `sentiment_card` · `event_impact_card` | 时机 / 催化剂 / 情绪 |
| Risks & Moat | `risk_factors_card` · `risk_yoy_diff_card` (+ pro-locked) · `moat_analysis_card` (+ pro-locked) | 风险与护城河 |
| Sources | `source_table` + 推理 trace（per-node accordion） | 透明度 / 较真用户 |

映射在 `frontend/src/components/canvas/tab-groups.ts` 单一来源。新分析卡只需在该文件加映射即可。

### Hero 字段派生（无重算）

`deriveHero(components)` 从已经在 canvas 上的 `ComponentInstruction[]` 派生 12 字段：

- `signalLabel` / `signalKind`: 优先 `investment_thesis_card.recommendation`（Strong Buy/Buy/Hold/Reduce/Sell），fallback `strategy_dashboard.signal`（Deep Value/Undervalued/Fair Value/Overvalued）— Free 用户无 thesis card 时仍能显示信号
- `marginOfSafety` / `upside` / `currentPrice` / `intrinsicValue` / `suggestedEntry`: `strategy_dashboard`
- `confidence` / `thesisHeadline`: `investment_thesis_card`
- `highSeverityRiskCount` / `totalRisksReported`: `risk_factors_card.top_risks` 中 `severity == "high"` 计数

Hero 直接读 props，不重计算。Tab 内卡片显示完整数据；hero 是"电梯演讲"摘要。

### Conversation panel 状态机

```
idle ──submit──▶ streaming（420px 满展开，进度+推理可见）
                    │
              status===complete
                    ▼
           collapsed（56px 轨：avatar + Ask icon）
                    │
              user click rail
                    ▼
            expanded as overlay（不挤压 canvas，420px 浮层）
                    │
              点遮罩 / 点 X
                    ▼
                  rail
```

派生态实现（不用 setState-in-effect）：
```
isStreaming = displayStatus === "connecting" || "connected"
showRail    = !isStreaming && ticker !== null
showOverlay = showRail && overlayOpen
```

`overlayOpen` 是唯一用户驱动的标志，由 rail 点击 + 遮罩点击驱动；其余由 displayStatus 派生。

### 流式 UX 细节

- **Tabs 不自动切换** — 抢焦点是反 UX。新卡片到达非活动 tab 时，tab 标题脉冲红点；用户主动点击。
- **Hero 渐入** — signal 先到、MoS 次到、thesis 最后；3 秒就能看到答案在成型。
- **Risks 块** — `highSeverityRiskCount > 0` 时变红，可点跳 Risks tab。
- **CanvasTabs `seenCounts` lazy-init** — 全 tab 用挂载时 group counts 初始化，pulse-dot 仅对**之后**到达的卡片触发；缓存视图（一次性全部到位）不显示假新卡提示。
- **`<AnalysisCanvas key={activeEntryId}>`** — 历史切换时 `seenCounts` / `activeTab` 等内部状态干净重置。

### 新增/修改文件

参见 [CHANGELOG.md `v0.8.0`](CHANGELOG.md#v080--verdict-first-ui-重构phase-1) 的"前端变更"节。

---

## 16. Save Thesis + Share（v0.9.0）

第一个粘性钩子：把 canvas 的当前状态钉成 snapshot，几周后回访可以看到关键字段如何漂移；同时 `/s/<uuid>` 可以把这份 snapshot 公开分享给非用户。

### 数据模型

```
saved_theses
├── id              uuid v4 (string)            非可遍历
├── user_id         FK users.id (CASCADE)       owner
├── ticker          string(8)                   AAPL / MSFT / ...
├── title           string(200) | null          可选（v0.9 暂未暴露 UI）
├── is_public       boolean (default true)      flip 即变私有
├── hero_snapshot   JSONB                       HeroSnapshot 全部 12 字段
├── components_snapshot JSONB                   ComponentInstruction[] 完整列表
└── created_at      timestamptz
```

### API 表面

| 端点 | 授权 | 行为 |
|---|---|---|
| `POST /api/saved-thesis` | required | body 含 `ticker / title? / is_public? / hero_snapshot / components_snapshot`；返回完整 payload |
| `GET /api/saved-thesis` | required | 返回 `{items: [SavedThesisSummary]}`（不带 components） |
| `GET /api/saved-thesis/{id}` | required | owner 才能读，否则 404 |
| `DELETE /api/saved-thesis/{id}` | required | 204 |
| `GET /api/share/thesis/{id}` | **none** | 仅 `is_public=true` 才返回，否则 404 |

### Frontend 数据流

```
verdict-hero.tsx
  └ useSavedTheses().items.find(t => t.ticker === current)
     └ <SavedDiffStrip saved=. current=f /> 
          (只在 status=='complete' && !isSnapshotView 时渲染)

hero-actions.tsx (HeroActions → SaveButton)
  └ useSavedTheses().save({ ticker, hero_snapshot: f, components_snapshot })
  └ 已 saved 后切换为 [Saved][Share]，Share 复制 /s/<uuid>

app/s/[id]/page.tsx
  └ getPublicThesis(id) → SavedThesisFull
  └ 渲染 <VerdictHero isSnapshotView /> + <CanvasTabs />
```

### Sidebar 二级段落

```
Sidebar
├── New analysis (button)
└── (scrollable middle)
    ├── Saved theses                  ← v0.9
    │   └── AAPL · BUY · 3w ago  [外链图标]  [X 悬停删除]
    └── (history groups)
        └── Today / Yesterday / This week / Earlier
```

点击 saved 行：仅 `is_public=true` 时新窗口打开 `/s/<id>`（私有 row 当前禁用导航；UI gap，待补）。

### 关键决策

- **UUID v4 主键** — share URL 非可遍历
- **JSONB 而非规范化表** — 每次分析都是 immutable snapshot，规范化收益小
- **`isSnapshotView` prop** — 防止跨用户跨时间无意义 diff（你访问别人的 AAPL share 时，"你自己的 saved AAPL" 不应被 diff）
- **`is_public` 默认 true** — 保存的本意通常是分享，private 是少数
- **乐观 UI** — save/remove 不等列表刷新；失败由 catch 兜底（v0.9 仅 console.warn，未来加 toast）

---

## 17. Watchlist + Follow-up Q&A（v0.10.0）

留存层闭环 + Pro 用户的对话式深挖入口。

### Watchlist 数据模型

```
watchlist_items
├── id              integer (auto)
├── user_id         FK users.id (CASCADE)
├── ticker          string(8)
├── target_mos_pct  float | null            "MoS ≥ X% 时告警"
├── created_at, updated_at, last_checked_at timestamptz
├── last_mos_pct, last_signal               cron 写回字段（v0.10 占位）
└── UNIQUE (user_id, ticker)
```

> 表在 v0.9 迁移中已创建；本版本启用 CRUD endpoint + UI。

### API 表面

| 端点 | 授权 | 行为 |
|---|---|---|
| `GET /api/watchlist` | required | 返回 `{items: [WatchlistItem]}` |
| `PUT /api/watchlist/{ticker}` | required | upsert（按 user_id+ticker 唯一）；`target_mos_pct` 验证 `[-100, 100]` |
| `DELETE /api/watchlist/{ticker}` | required | 204 |
| `POST /api/follow-up` | **require_pro** | body `{ticker, question, hero_snapshot?, components_snapshot[]}` → `{answer, tab_hint, confidence}` |

### Follow-up Q&A 流程

```
用户在 overlay conversation 输入问题
   ↓
askFollowUp() POST /api/follow-up
   ↓
backend:
   1. require_pro gate（401/403）
   2. BUCKET_RECALCULATE rate limit（30/day per IP，与 DCF recalc 共池）
   3. bind_client_ip → 计费归属用户
   4. _hero_summary + _components_summary 拼 prompt 变量（components 截 12 张）
   5. complete_json("follow_up", v=1, FollowUpAnswer)
   6. 返回 {answer, tab_hint, confidence}
   ↓
frontend:
   thread.push({state: ok, answer})
   tab_hint 严格 5 选 1 验证 → "See Valuation tab →" 可点击
```

### Prompt 模板（`follow_up_v1.yaml`）

- temperature 0.4 / max_tokens 1200
- System prompt 边界：
  - 仅基于 payload 内容回答，不臆造数据
  - what-if 类问题做方向性推理而非编造精确数字
  - 1-3 短段落，无 heading
  - `<<<USER_CONTENT>>>` / `<<<END_USER_CONTENT>>>` 标记 + DATA-only 反注入
  - JSON schema 强约束 `tab_hint ∈ verdict|valuation|strategy|risks|sources|null`

### 状态提升：activeTab from AnalysisCanvas → AppShell

```
AppShell
├── overlayOpen: boolean         （rail vs overlay panel）
├── activeTab: TabId             ← v0.10 lift up
├── handleJumpToTab(t)           setActiveTab(t) + setOverlayOpen(false)
│
├── <ConversationPanel components onJumpToTab={handleJumpToTab} />
│       └── <FollowUpSection key={ticker} ...>
│              └── tab_hint button → calls onJumpToTab(validTab)
│
└── <AnalysisCanvas activeTab onTabChange />
       └── <VerdictHero onJumpToTab={onTabChange} />（risks badge）
       └── <CanvasTabs activeTab onTabChange />
```

`activeTab` 提升使两个独立组件树（conversation overlay、canvas）能互相切 tab。

### 竞态修复：AbortController 在 saved-thesis + watchlist contexts

```
const inflightRef = useRef<AbortController | null>(null);

const refresh = useCallback(async () => {
  inflightRef.current?.abort();             // 1. cancel prev
  if (status !== "authenticated") {
    setItems([]); return;                    // logout 立即清空
  }
  const c = new AbortController();
  inflightRef.current = c;
  try {
    const fresh = await listX(c.signal);
    if (!c.signal.aborted) setItems(fresh);  // 2. post-await aborted check
  } catch { /* AbortError or network */ }
  finally {
    if (inflightRef.current === c) {         // 3. 不污染更新 controller
      inflightRef.current = null;
      setLoading(false);
    }
  }
}, [status]);

useEffect(() => () => inflightRef.current?.abort(), []);  // unmount cleanup
```

防止 logout 时 prev auth'd fetch 的 200 响应在 logout 后回来 setItems(authData) 覆盖 setItems([])。

### 关键决策

- **Pro gate on `/api/follow-up`** — 与 Pro LLM 节点等级一致；free 用户得 403 friendly upgrade message
- **Watchlist 点击 = 重分析** — 用户点 sidebar ticker 想看最新数据，不是查看 watchlist 历史
- **FollowUpSection `key={ticker}`** — ticker 切换时 thread / input state 干净重置
- **`hasPending` 阻塞双提交** — `idx = thread.length` 闭包+连按 Enter 会让两个 setState 落到同一 thread 槽
- **客户端 [-100, 100] 验证** — 后端 422 静默吞会让用户以为已加 watch，前端范围检查 + 红框 + disable 提交避免
