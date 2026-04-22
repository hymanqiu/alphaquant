# AlphaQuant 更新日志

本文件记录项目的所有重要变更。

## 版本总览

| 版本 | 日期 | 类型 | 变更摘要 |
|------|------|------|----------|
| v0.4.0 | 2026-04-22 | feat | 事件影响分析：两步 LLM 筛选重大新闻 → 自动调整 DCF 参数 → 重算内在价值。改进新闻获取（7天分批、公司名匹配、权威来源白名单、SEC 8-K 整合） |
| v0.3.0 | 2026-04-21 | feat | 消息面情绪修正：Finnhub 新闻 + 内部人情绪 → 综合评分 → 安全边际调整。新增 Finnhub 客户端、DeepSeek LLM 情绪分析、sentiment_card 组件 |
| v0.2.0 | 2026-04-17 | feat | 相对估值（市场乘数法）：当前乘数 + 历史百分位 + 同业对比。新增 FMP API 客户端、relative_valuation_card 组件 |
| v0.1.0 | 2026-04-17 | — | 初始版本：SEC EDGAR 数据获取、财务健康扫描、DCF 估值建模、买入策略、数据溯源、SSE + Generative UI |

## v0.4.0 — 事件影响分析（Event Impact Analysis）

**日期：** 2026-04-22

### 概要

在消息面情绪分析基础上，新增事件影响分析节点。通过两步 LLM 调用，从权威新闻和 SEC 8-K 文件中筛选出真正影响估值的重大事件，自动调整 DCF 参数并重算内在价值。同时大幅改进了新闻获取和过滤机制：公司名匹配、7 天分批获取确保 30 天覆盖、权威来源白名单、SEC 8-K 文件整合。分析管线从 7 个节点扩展至 8 个节点。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 事件影响 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/event_impact.py` | 事件影响分析节点（约 490 行）。两步 LLM 调用：(1) 筛选有估值影响的新闻 (2) 分析参数调整。应用调整后调用 `compute_dcf()` 自动重算。发射 `event_impact_card` 组件。 |
| `backend/backend/agents/nodes/event_impact_math.py` | 纯计算函数（无 I/O）：`PARAMETER_REGISTRY` 参数注册表、`apply_parameter_adjustment()` 单参数调整、`apply_all_adjustments()` 全参数映射（含扩展参数：risk_adjustment→WACC、revenue_adjustment→增长、margin_adjustment→增长*0.5、fcf_one_time_adjust→FCF）、`recalculate_dcf()` 调用已有 DCF 模型、`validate_filter_response()` 和 `validate_analysis_response()` 校验 LLM 返回值。 |
| `backend/tests/agents/nodes/test_event_impact_math.py` | 事件影响数学函数的单元测试，覆盖参数调整、映射逻辑、DCF 重算和校验函数。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `event_impact_result: dict[str, Any] | None` 字段。 |
| `backend/backend/agents/value_analyst.py` | 导入 `event_impact_node`，新增节点，修改边：`event_sentiment` → `event_impact` → `strategy`。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `event_impact_result: None`。 |
| `backend/backend/agents/nodes/strategy.py` | 优先使用 `event_impact_result.recalculated_dcf.intrinsic_value_per_share`（如存在），否则回退到原始 `dcf_result`。新增 `event_impact_result` 参数传入 `_run_strategy`。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中追加事件影响摘要，如有重算 DCF 使用新的内在价值。 |
| `backend/backend/main.py` | 导入 `close_event_impact_client`，在 lifespan shutdown 中调用。 |
| `backend/backend/services/finnhub_client.py` | `get_company_news()` 从单次请求改为 7 天分批并发获取（semaphore=3），按 `id` 去重，按 `datetime` DESC 排序，确保 30 天完整覆盖。 |
| `backend/backend/agents/nodes/event_sentiment_math.py` | 新增 `TICKER_ALIASES`（40+ ticker→公司名映射）、`_headline_mentions_ticker()` 词边界匹配含公司名、`_text_mentions_ticker()` 摘要检查、改进 `_compute_relevance_score()` 新评分体系（4/3/2/0）、`filter_by_authoritative_source()` 白名单过滤（Reuters/Bloomberg/WSJ/FT 等 20+ 权威来源）、`_extract_article_timestamp()` 日期提取排序。删除未使用的 `_headline_mentions_other_ticker()` 和不可达的死代码分支。 |
| `backend/backend/agents/nodes/event_sentiment.py` | 新增 SEC 8-K 文件获取（通过 `sec_client.get_recent_8k_filings()`），转为 article 格式并入文章列表。新增 `_log_date_distribution()` 调试日志。LLM 分析上限从 15 篇提升到 20 篇。 |
| `backend/backend/services/llm_sentiment.py` | LLM 文章上限从 15 提升到 20，`max_tokens` 从 2000 提升到 2500。`_validate_llm_response()` 改为创建副本避免修改原 dict。SYSTEM_PROMPT 要求 `key_events` 按重要性排序。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/event-impact-card.tsx` | 事件影响可视化卡片（约 320 行）。包含：摘要 + 置信度指示器、参数对比表（Original → Adjusted + delta 箭头 + reasoning tooltip）、重算内在价值显示、触发事件列表（可点击链接 + 来源 + 日期）。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `event_impact_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "event_impact", label: "Analyzing Event Impact" }`（位于 `event_sentiment` 和 `strategy` 之间）。 |

### 两步 LLM 分析流程

```
Step 1 — 筛选: 输入所有文章 → LLM 排除常规分析师评级/泛市场评论/已定价业绩
                       → 返回 impactful_indices + reasoning
Step 2 — 分析: 输入筛选文章 + 当前 DCF 假设 → LLM 返回参数调整建议
                       → 每个参数: {type: "delta"/"multiplier"/"absolute", value, reasoning} | null
```

### 参数调整映射

| 直接参数 | 调整方式 | 作用于 |
|----------|----------|--------|
| growth_rate | delta (%) | FCF 增长率 |
| terminal_growth_rate | delta (%) | 永续增长率 |
| discount_rate | delta (%) | WACC/折现率 |

| 扩展参数 | 映射方式 | 实际影响 |
|----------|----------|----------|
| risk_adjustment | 累加到 discount_rate | 风险溢价变化 |
| revenue_adjustment | 乘到 growth_rate | 收入轨迹调整 (0.95 = 减 5%) |
| margin_adjustment | 0.5x 权重加到 growth_rate | 利润率变化部分传导到 FCF |
| fcf_one_time_adjust | 直接替换 latest_fcf | 一次性 FCF 调整 |

### 新闻过滤改进

| 改进项 | 说明 |
|--------|------|
| 公司名匹配 | 40+ ticker→公司名映射 (NVDA→"nvidia", AAPL→"apple")，词边界正则 |
| 相关度评分 | 4=标题含ticker/公司名, 3=summary+related, 2=唯一related, 0=排除 |
| 权威来源白名单 | Reuters/Bloomberg/WSJ/FT/CNBC 等 20+ 家 (SEC 8-K 始终保留) |
| 7天分批获取 | 解决 Finnhub 单次请求结果上限问题，确保 30 天覆盖 |
| SEC 8-K 整合 | 获取最近 30 天 8-K 文件，转为 article 格式，高优先级处理 |
| 双排序 | 相关度 DESC + 日期 DESC，max_articles=30 |

### 代码质量修复（审核后）

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `close_event_impact_client()` 未在 main.py shutdown 中调用 | HIGH | 添加到 lifespan shutdown |
| `_compute_relevance_score` 中 `ticker_in_related` 检查位于 `not ticker_in_related` 分支内（不可达代码） | HIGH | 移除不可达分支 |
| 未使用的 `_headline_mentions_other_ticker()` 函数 | HIGH | 删除死代码 |
| `_validate_llm_response()` 就地修改传入的 dict | HIGH | 创建 shallow copy 避免修改原 dict |
| `event_impact.py` 中 LLM 返回的索引未过滤负数 | MEDIUM | `if 0 <= i < len(articles)` 替代 `if i < len(articles)` |

### 测试

所有 133 个后端测试通过，包括：
- 新增 `test_event_impact_math.py` 覆盖事件影响数学函数
- `test_event_sentiment_math.py` 新增 8 个测试覆盖公司名匹配、日期排序、summary 字段
- 新增 `TestFilterByAuthoritativeSource` 覆盖权威来源过滤

---

## v0.3.0 — 消息面情绪修正（Event & Sentiment Integration）

**日期：** 2026-04-21

### 概要

新增消息面情绪分析管线，通过 Finnhub（Free plan）获取近期新闻和内部人交易数据，使用 DeepSeek LLM 对新闻进行情绪打分（因 Finnhub `news-sentiment` 为 Premium 功能），综合计算整体情绪评分并调整策略节点的安全边际信号。分析管线从 5 个节点扩展至 7 个节点。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 相对估值 → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 消息面情绪 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/services/finnhub_client.py` | Finnhub HTTP 客户端（懒初始化 `httpx.AsyncClient`）。三个方法：`get_company_news()` 获取 30 天新闻（Free）；`get_news_sentiment()` Premium 情绪数据（Free plan 优雅降级）；`get_insider_sentiment()` 内部人情绪（Free）。 |
| `backend/backend/services/llm_sentiment.py` | DeepSeek LLM 新闻情绪分析。通过 OpenAI 兼容 API 调用 `/chat/completions`，使用 XML 标签 `<articles>` 防止 prompt injection，返回结构化 JSON。包含 `_validate_llm_response()` 校验函数（限制 overall_score ∈ [-1, 1]、confidence ∈ [0, 1]）。 |
| `backend/backend/agents/nodes/event_sentiment.py` | 消息面情绪核心节点。获取新闻 → 尝试 Premium 数据 → LLM 降级分析 → 获取内部人数据 → 综合评分 → 发射 `sentiment_card` 组件。 |
| `backend/backend/agents/nodes/event_sentiment_math.py` | 纯计算函数（无 I/O）：`compute_overall_sentiment()` 60/40 新闻/内部人加权；`compute_sentiment_adjustment()` 安全边际修正（±8%）；`classify_event_type()` 关键词分类。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/main.py` | 导入 `finnhub_client`，在 `lifespan()` 关闭时添加 `await finnhub_client.close()`。 |
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `event_sentiment_result: dict[str, Any] | None` 字段（位于 `relative_valuation_result` 和 `strategy_result` 之间）。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `event_sentiment_result: None`。 |
| `backend/backend/agents/value_analyst.py` | 导入 `event_sentiment_node`，将 `event_sentiment` 节点接入 `relative_valuation` 和 `strategy` 之间。 |
| `backend/backend/agents/nodes/strategy.py` | 新增情绪修正逻辑：读取 `event_sentiment_result`（作为参数传入），提取 `margin_of_safety_pct_delta`，调整安全边际。`_run_strategy` 新增 `event_sentiment_result` 参数。`strategy_result` 新增 `sentiment_delta` 和 `sentiment_note` 字段。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中新增消息面情绪摘要（如 "Event sentiment: Bullish (score: 0.38)"）。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/sentiment-card.tsx` | React 组件（约 487 行），包含三个区块：(A) 情绪仪表盘——半圆形 SVG 仪表（bearish 红 → neutral 黄 → bullish 绿）；(B) 新闻细分——看多/中性/看空分布条、关键事件列表、文章列表（含情绪点、事件类型徽章）；(C) 内部人情绪——MSPR 进度条（-100 到 +100）和净变动。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `sentiment_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "event_sentiment", label: "Analyzing Event Sentiment" }`（位于 `relative_valuation` 和 `strategy` 之间）。 |

### 情绪评分机制

| 数据源 | 权重 | 评分范围 | 获取方式 |
|--------|------|----------|----------|
| 新闻情绪 | 60% | -1.0 到 +1.0 | Finnhub Premium 或 DeepSeek LLM |
| 内部人情绪 | 40% | -1.0 到 +1.0 | Finnhub Free `/stock/insider-sentiment` |

### 安全边际修正规则

| 情绪评分范围 | 标签 | MoS 修正 |
|-------------|------|---------|
| < -0.5 | Very Bearish | -8%（提高买入门槛） |
| -0.5 to -0.2 | Bearish | -4% |
| -0.2 to +0.2 | Neutral | 0% |
| +0.2 to +0.5 | Bullish | +3%（降低买入门槛） |
| > +0.5 | Very Bullish | +5% |

### 降级策略

| 场景 | 行为 |
|------|------|
| 未设置 `AQ_FINNHUB_API_KEY` | 节点跳过，不影响后续分析 |
| Finnhub Free plan（无 Premium 情绪） | 自动使用 LLM 分析新闻 |
| 未设置 `AQ_LLM_API_KEY` / `AQ_LLM_BASE_URL` | LLM 不可用，使用关键词分类 |
| Finnhub 无新闻数据 | news_score = None，仅使用内部人情绪 |
| Finnhub 无内部人数据 | insider_score = None，仅使用新闻情绪 |
| 两者均无数据 | 整体评分为 0 (Neutral)，无修正 |

### 配置

在 `.env` 文件中新增以下配置（均已在 `config.py` 中定义）：
```
AQ_FINNHUB_API_KEY=<your-key>            # 必需: 启用消息面情绪节点
AQ_LLM_API_KEY=<your-deepseek-key>       # 可选但推荐: LLM 新闻情绪分析
AQ_LLM_BASE_URL=https://api.deepseek.com # 可选: OpenAI 兼容 API 地址
AQ_LLM_MODEL=deepseek-chat               # 可选: 模型名称
```

### 测试

新增 35 个单元测试（`backend/tests/agents/nodes/test_event_sentiment_math.py`），覆盖：
- `compute_sentiment_adjustment` 边界值（极端看空 -8% 到极端看涨 +5%）
- `compute_overall_sentiment` 加权逻辑（仅新闻、仅内部人、两者均有、无数据）
- `classify_event_type` 关键词分类（8 种事件类型 + 18 个参数化测试用例）
- 所有 51 个后端测试通过（35 新增 + 16 原有）

### 代码质量修复（审核后）

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `strategy.py` 中 `_run_strategy` 引用未传入的 `state` 变量 | CRITICAL | 将 `event_sentiment_result` 作为显式参数传入 `_run_strategy` |
| LLM 响应仅检查 `overall_score` 是否存在 | HIGH | 新增 `_validate_llm_response()` 校验所有字段类型和范围 |
| LLM 错误响应体被记录到日志（可能泄露敏感信息） | HIGH | 移除 `e.response.text[:200]` 日志，仅记录状态码 |
| 新闻标题直接拼接进 LLM prompt（prompt injection 风险） | HIGH | 使用 `<articles>` XML 标签包裹用户内容 |
| 未使用的 `entity_name` 变量 | MEDIUM | 删除死代码 |

---

## v0.2.0 — 相对估值（市场乘数法）

**日期：** 2026-04-17

### 概要

新增完整的相对估值分析管线，使用市场乘数（Market Multiples）进行自历史对比和同业对比，与现有 DCF 绝对估值形成互补。分析流程现在会产出第二份独立的估值参考意见。

### 管线变更

```
变更前: SEC数据 → 财务健康 → DCF → 策略 → 逻辑溯源
变更后: SEC数据 → 财务健康 → DCF → 相对估值 → 策略 → 逻辑溯源
```

### 后端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/relative_valuation.py` | 相对估值核心节点（约280行）。计算当前乘数（P/E、P/B、P/S、EV/Revenue、EV/EBIT、EV/FCF、PEG）、历史百分位分析、以及通过 FMP API 的同业对比。向 SSE 流发送 `relative_valuation_card` 组件。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `backend/backend/services/market_data.py` | 新增3个 FMP API 方法：`get_peers()` 通过 `/api/v4/stock_peers` 获取同业股票代码；`get_peer_key_metrics_ttm()` 通过 `/api/v3/key-metrics-ttm` 获取 TTM 关键指标；`get_batch_peer_metrics()` 使用 `asyncio.gather` 进行并发批量查询。 |
| `backend/backend/models/agent_state.py` | 在 `AnalysisState` 中新增 `relative_valuation_result: dict[str, Any] | None` 字段。 |
| `backend/backend/agents/value_analyst.py` | 在 LangGraph 管线中，将 `relative_valuation` 节点接入 `dynamic_dcf` 和 `strategy` 之间。 |
| `backend/backend/api/routes.py` | 初始状态字典中新增 `relative_valuation_result: None`。 |
| `backend/backend/agents/nodes/logic_trace.py` | 最终结论（verdict）中新增市场乘数摘要（P/E、P/B、P/S），在数据可用时自动包含。 |
| `backend/backend/agents/nodes/strategy.py` | 新增相对估值交叉校验：若同业 P/E 偏差超过 ±20%，生成推理说明。`_run_strategy` 新增 `relative_valuation_result` 参数。 |
| `backend/backend/config.py` | 新增 `.env` 文件自动发现机制（从 `config.py` 向上逐级搜索至仓库根目录），无需手动设置环境变量即可加载 `AQ_FMP_API_KEY`。 |

### 前端变更

#### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/analysis/relative-valuation-card.tsx` | React 组件（约340行），包含三个区块：(A) 当前乘数网格——展示 P/E、P/B、P/S、EV/Revenue、EV/EBIT、EV/FCF、PEG 及百分位指示器；(B) 历史百分位条形图——按颜色区分估值区间；(C) 同业对比表——目标公司、同业行、行业中位数行。 |

#### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/component-registry.ts` | 注册 `relative_valuation_card` 组件，支持懒加载。 |
| `frontend/src/hooks/use-analysis-stream.ts` | 在管线步骤中新增 `{ node: "relative_valuation", label: "Comparing Market Multiples" }`。 |

### 降级策略

| 场景 | 行为 |
|------|------|
| 未设置 `AQ_FMP_API_KEY` | 节点跳过所有依赖价格的乘数计算，返回 `price_available: false`。前端显示提示横幅。 |
| 已设置 FMP Key 但未找到同业 | 跳过同业对比，返回 `peer_data_available: false`。前端隐藏同业表格。 |
| 数据完整 | 完整分析：当前乘数、历史百分位、同业偏差百分比对比。 |

### 配置

项目根目录新增 `.env` 文件（已被 git 忽略）：
```
AQ_FMP_API_KEY=<your-key>
```

### 代码质量修复（审核后）

v0.2.0 通过代码审核后修复了以下问题：

| 问题 | 严重度 | 修复 |
|------|--------|------|
| `peer_comparison` dict 被就地修改 | HIGH | 改为展开运算符创建新对象 `{**peer_comparison, "deltas": deltas}` |
| relative_valuation 与 strategy 各自独立调用 FMP API | HIGH | strategy 优先从 relative_valuation_result 中读取 current_price 和 annual_prices，避免重复请求 |
| 所有 FMP API 方法静默吞掉异常 | HIGH | 改为精确捕获（`httpx.HTTPStatusError`、`httpx.RequestError`、`KeyError/ValueError/TypeError`）并记录 `logging.warning` |
| SSE 错误事件泄露内部异常信息 | HIGH | 前端只显示通用消息，完整异常通过 `logger.exception()` 记录到服务端 |
| `httpx.AsyncClient` 在模块导入时创建 | HIGH | 改为懒初始化，首次使用时创建 |
| FMP 历史行情依赖 API 排序但未验证 | MEDIUM | 显式 `sorted(data, key=lambda e: e["date"], reverse=True)` 排序 |
| 同业对比表目标行只显示 delta% | MEDIUM | 改为同时显示绝对乘数值和偏差百分比 |
| 文件行数超过 400 行建议上限 | MEDIUM | 提取 `relative_valuation_math.py`（纯计算函数），主节点从 422 行降至 251 行 |
| 旧节点（financial_health/dcf_model/logic_trace）泄露异常信息 | HIGH | 统一使用通用错误消息 + 服务端日志 |
| DCF 重算端点未校验参数可导致 ZeroDivisionError | HIGH | `DCFRecalculateRequest` 新增 `discount_rate > terminal_growth_rate` 校验 |
| FMP 同业 API 可能返回目标公司自身 | HIGH | `get_peers()` 过滤掉与目标相同的 ticker |

### 新增文件（审核后）

| 文件 | 说明 |
|------|------|
| `backend/backend/agents/nodes/relative_valuation_math.py` | 纯计算函数（无 I/O）：`compute_current_multiples`、`compute_historical_multiples`、`percentile_rank` 等 |

---

## v0.1.0 — 初始版本

**日期：** 2026-04-17

### 概要

白盒 AI 投资研究系统的首个版本。从 SEC EDGAR 获取财务报告数据，通过 LangGraph 状态机执行多步骤价值分析，并经由 SSE 将推理过程和分析结果以 Generative UI 组件的形式实时推送到 Next.js 前端。

### 技术架构

- **后端：** Python / FastAPI / LangGraph / pydantic-settings
- **前端：** Next.js 16 / React / shadcn-ui / SSE

### 后端功能

- **SEC EDGAR 管线：** `TickerResolver` 将股票代码映射为 CIK，`SECClient` 从 EDGAR API 抓取数据（10次/秒限速），`sec_agent.py` 使用 XBRL 标签回退链对数据进行标准化处理。
- **财务健康节点：** 利息覆盖率、负债权益比、利润率（毛利率/营业利润率/净利率）、营收年复合增长率（3年/5年）、净资产收益率（ROE）、综合健康评级。
- **DCF 模型节点：** 自由现金流预测、终值计算、贴现率、每股内在价值。支持通过 `POST /api/recalculate-dcf` 用用户调节的参数重新计算。
- **策略节点：** 安全边际、P/E 百分位分析、入场信号（深度价值 / 低估 / 合理 / 高估）、建议入场价格。
- **逻辑溯源节点：** 将每个指标映射回其 SEC 文件来源，构建源文件 URL，生成最终分析结论。

### 前端功能

- 基于 SSE 的流式传输，使用 `useSSE` 和 `useAnalysisStream` 自定义 Hook
- 9 个通过组件注册表懒加载的分析组件
- 带打字机效果的 Agent 终端
- 显示管线步骤的进度追踪器
- DCF 假设滑块，支持实时重算

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analyze/{ticker}` | GET | SSE 流，触发完整 LangGraph 分析 |
| `/api/recalculate-dcf` | POST | 用用户调节的参数重新计算 DCF |

### LangGraph 管线

```
START → fetch_sec_data → [错误→END] → financial_health_scan → dynamic_dcf → strategy → logic_trace → END
```
