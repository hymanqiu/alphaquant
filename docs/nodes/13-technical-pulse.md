# Node 13: technical_pulse

> 图位置: `strategy → technical_pulse → qualitative_analysis`

## 职责

生成"币圈达成看板风格"的技术面 + 大盘 + 情绪面快照，作为 Free tier 与 Pro tier 之间的产品差异化补充层。**0 LLM 调用**——纯规则计算，全局 LLM 预算耗尽时仍可用。详见 [ADR 013](../decisions/013-pulse-tab.md)。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials \| None` | ✅ | 取 `ticker` / `entity_name` |
| `user_tier` | `str` | – | 不参与门控（Free 也可跑）|

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `pulse_result` | `dict[str, Any] \| None` | 序列化的 `TechnicalPulse`；任一前提失败 → `None` |
| `reasoning_steps` | `list[str]` | 追加一条 |

### `TechnicalPulse` 结构体

> **定义**: `backend/models/technicals.py`

```python
class TechnicalPulse(BaseModel):
    composite_score: int                     # 0–100
    signal_label: SignalLabel                # "Strong Sell"|"Sell"|"Neutral"|"Buy"|"Strong Buy"
    bull_signal_count: int
    bear_signal_count: int
    bullish_pct: float                       # 0.0–1.0

    indicators: list[TechnicalIndicator]     # 长度 4: rsi / macd / ma_stack / wk52
    active_signals: list[TechnicalSignal]    # 触发的全部 11 条规则中的一部分
    market_context: MarketContext            # SPY / VIX / 10Y / DXY / sector ETF
    sentiment: SentimentSignals              # F&G / Put-Call / insider 90d / short / AAII
    ohlcv: list[OHLCV]                       # ~252 daily bars (1Y)
    ohlcv_ma20: list[float | None]           # 同长，前 19 None
```

## 核心算法

### 11 条规则 + 评分

```
detect_signals(closes, highs, lows, volumes, spy_closes) → list[TechnicalSignal]
  ├── 8 bull: golden_cross / macd_bullish_crossover / higher_highs_lows
  │           / volume_confirms_trend / above_all_mas / relative_strength
  │           / breakout_base / above_vwap
  └── 3 bear: rsi_overbought / rsi_bearish_divergence / distribution_days

composite_score(signals) = round(50 + 50 * tanh(Σ(±weight) / 4))
  → 评分范围 [0, 100]，中性 50，±8 大致饱和

signal_label(score):
  < 30 → Strong Sell
  < 45 → Sell
  < 55 → Neutral
  < 70 → Buy
  其余 → Strong Buy
```

完整规则阈值与权重见 [ADR 013 §4.4](../decisions/013-pulse-tab.md#44-信号规则全表)。

### 数据获取顺序（串行 async）

```
1. fetch_history(ticker, 370d)   ←  必需。失败 → 整节点 skip
2. fetch_history("SPY", 370d)    ←  缺则 relative_strength 不触发，其它正常
3. market_data_client.get_company_profile(ticker)  → sector → SPDR ETF
4. fetch_quote("SPY") / "^VIX" / "^TNX" / "^DXY"|"DXY" / sector ETF
5. fetch_insider_net_90d(ticker) ←  Finnhub /stock/insider-transactions
6. fetch_fear_greed()            ←  CNN production.dataviz.cnn.io
```

`^TNX` 自适应：值 > 20 视为 CBOE 原生（yield × 10）→ 自动 ÷10；FMP 已归一化的 `4.25` 直接通过。

### TTL 缓存

`technicals_data.py` 顶部定义 `@_cached(ttl=300s)` 装饰器，应用到 4 个 fetcher（`fetch_history` / `fetch_quote` / `fetch_insider_net_90d` / `fetch_fear_greed`）。设计要点：

- **Key 来源**：所有非 `httpx.AsyncClient` 的 args + 排序后的 kwargs。每次调用传不同的 transient client 不会破坏缓存
- **失败不缓存**：返回值经 `_is_empty_result()` 判断（`None` / 空 list / 全 None 的 tuple）→ 跳过缓存写入，下次调用仍重试
- **粒度**：每个 decorated 函数独立 closure，互不污染
- **效果**（同 IP 5 min 内）：
  - 同 ticker 重新分析：FMP 调用 **7 → 0**（全命中）
  - 不同 ticker：FMP 调用 **7 → 3**（仅 ticker 自身 history + sector quote + insider 不命中）
- **进程级**：uvicorn `--reload` 重启或多 worker 部署时各自独立。本地测试足够；生产环境想跨 worker 共享需上 Redis（v0.11 不需）

## emit 的 SSE 组件

| component_type | 前端 |
|----------------|------|
| `pulse_score_hero` | 综合评分 + signal label badge + bull/bear 力量条 |
| `price_chart_card` | 1Y 蜡烛 + MA20 紫线 + 25% 高度 volume + 3M/6M/1Y 切换（lightweight-charts v5）|
| `indicator_grid_card` | RSI 14 / MACD hist / MA stack / 52W position 四张迷你卡 |
| `signal_chips_card` | 触发信号 chips（绿=bull、红=bear，hover tooltip 显示 detail）|
| `market_context_card` | SPY / VIX / 10Y / DXY / 板块 ETF 五项快照 |
| `sentiment_pulse_card` | F&G 半圆渐变仪表盘 + Put/Call · Insider · Short · AAII |

## 关键假设

- **OHLCV 是必需的**——取 1 年（370 个日历日 ≈ 252 交易日）作为所有指标的输入。少于 50 bars → 整节点 skip。
- **指标本地计算**——RSI/MACD/SMA/EMA/VWAP 都在 `technical_pulse_math.py` 手写（无 pandas-ta），这样可单测、依赖少。
- **板块 ETF 映射**——FMP profile.sector 字符串 → SPDR sector ETF 的 11 项映射表（`technicals_data.py::_SECTOR_ETF`），未识别 → 回退 `SPY`。
- **AAII 暂未接**——v0.11 留 None 占位，下版本注册账号后补。

## 失败模式与降级

| 场景 | 处理 | 前端表现 |
|------|------|----------|
| `AQ_FMP_API_KEY` 空 | `step_complete(skipped=True)` + return `None` | Pulse tab 0 卡 |
| OHLCV 拉取失败 / 不足 50 bars | 同上 | Pulse tab 0 卡 |
| `AQ_FINNHUB_API_KEY` 空 | `sentiment.insider_net_usd_90d = None` | "Insider net (90d)" 显示 "—" |
| VIX/10Y/DXY 任一拉取失败 | 该字段 = None，节点继续 | Market context 对应 tile 显示 "—" |
| F&G 端点超时 / 403 | `sentiment.fear_greed_*` = None | F&G gauge 不绘指针，只显示渐变 arc |
| 节点抛任意异常 | `ErrorEvent(recoverable=True)` + return `None` | Pulse tab 空，下游 Pro 节点不受影响 |

## Pro 钩子（v1 占位、v1.1 实施）

ADR §4.8 列出 2 个未来 Pro 锁定卡——**v0.11 不实现**：
- `pulse_score_explainer_locked_card`：LLM 一句话解释为什么 Bullish
- `insider_detail_locked_card`：详细 insider 列表（人名、日期、股数）

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/technical_pulse.py` | 主节点（含 I/O，串行 async）|
| `backend/agents/nodes/technical_pulse_math.py` | 纯函数：5 indicator + 11 detector + 评分 + 4 indicator card builder |
| `backend/services/technicals_data.py` | FMP / Finnhub / CNN 数据访问层 + sector_to_etf 映射 |
| `backend/models/technicals.py` | 6 个 Pydantic 数据契约 |
| `backend/tests/agents/nodes/test_technical_pulse_math.py` | 17 个单测（仅 `_math` 部分，per 项目惯例）|

## 前端组件

| component_type | 组件 | 文件 |
|----------------|------|------|
| `pulse_score_hero` | `PulseScoreHero` | `frontend/src/components/pulse/pulse-score-hero.tsx` |
| `price_chart_card` | `PriceChartCard` + `PriceChartImpl` | 同上目录（dynamic + ssr:false 拆两文件）|
| `indicator_grid_card` | `IndicatorGridCard` | 同上 |
| `signal_chips_card` | `SignalChipsCard` | 同上 |
| `market_context_card` | `MarketContextCard` | 同上 |
| `sentiment_pulse_card` | `SentimentPulseCard` | 同上（含 SVG 半圆 F&G gauge）|

## ADR 参考

[ADR 013: Pulse Tab](../decisions/013-pulse-tab.md) — 决策摘要、信号规则全表、视觉规范、降级策略。
