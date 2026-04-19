# AlphaQuant 更新日志

本文件记录项目的所有重要变更。

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
