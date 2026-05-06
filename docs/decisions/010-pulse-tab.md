# ADR-010：Pulse Tab —— 技术指标 + 大盘 + 情绪 看板

> 状态：已批准，待实施
> 日期：2026-05-05
> 相关节点：`agents/nodes/technical_pulse.py`（新增第 13 节点）
> 相关 component_type：6 个新增（见 §5.1）

---

## 1. 背景与定位

现有 5 tab（Verdict / Valuation / Strategy / Risks & Moat / Sources）以基本面叙事为主，缺少**实时盘面感**。新增 Pulse tab，定位"币圈达成看板风格"的技术面与情绪面快照——

- 视觉参考：CoinGlass / TradingView heatmap / GMX dashboard 的暗色 + neon 调性
- 信息层级：综合评分 hero → K 线 → 4 张指标卡 → 信号 chips → 大盘条 → 情绪行
- 商业意义：填补 Free / Pro 之间的产品差距——技术面对 Free 用户也有用，但保留两个 Pro 钩子做差异化

---

## 2. 决策摘要

| 议题 | 结论 |
|---|---|
| 数据时效 | **一次性快照**：分析时拉一次（含 1Y OHLCV），前端切换 3M/6M/1Y 纯切片，不重拉 |
| 综合评分 | **纯规则加权 + tanh 归一**，不接入 LLM |
| K 线图库 | **`lightweight-charts`**（TradingView 出品，~50KB gzip） |
| Tier 分配 | 整个 tab **Free 可用**；预留 2 个 Pro 钩子但 v1 不实现 |
| 指标范围 | 11 条信号规则 + 4 个迷你指标 + 5 项大盘 + 4 项情绪 |
| 节点位置 | `strategy` 之后、`qualitative_analysis`（Pro）之前 |
| LLM 调用数 | **0**——这是 Pulse tab 最大的工程优势，全局预算耗尽时 Pulse 仍可用 |

---

## 3. 信息架构（top → bottom）

1. **Pulse Hero**——综合评分 0–100 大数字 + label badge（Strong Sell / Sell / Neutral / Buy / Strong Buy）+ 多空信号计数 + 多空力量条
2. **Price Chart Card**——K 线 + MA20 叠加 + 成交量；3M / 6M / 1Y 切换（前端切片）
3. **Indicator Grid Card**——4 张迷你卡：RSI · MACD histogram · MA stack · 52W position
4. **Signal Chips Card**——所有触发的 active signals，绿色 = bull、红色 = bear
5. **Market Context Card**——一行 5 项：SPY · VIX · 10Y yield · DXY · 所在板块 ETF
6. **Sentiment Pulse Card**——左：F&G gauge 半圆仪表盘；右：Put/Call · Insider 90d · Short interest · AAII 列表

`canvas/tab-groups.ts` 增加 `pulse` tab，插入位置：`['verdict', 'valuation', 'strategy', 'risks', 'pulse', 'sources']`

---

## 4. 后端实现

### 4.1 LangGraph 节点装配

`agents/value_analyst.py` 在现有图中插入：

```python
graph.add_node("technical_pulse", technical_pulse)
# 替换原 strategy → qualitative_analysis 边
graph.add_edge("strategy", "technical_pulse")
graph.add_edge("technical_pulse", "qualitative_analysis")
```

### 4.2 文件清单

```
backend/agents/nodes/technical_pulse.py            主节点（含 I/O）
backend/agents/nodes/_technical_pulse_math.py      纯函数：信号判定 + 评分
backend/services/data/technicals.py                FMP/Finnhub 数据访问层
backend/models/agent_state.py                      增加 TechnicalPulse 字段
backend/models/events.py                           （如需）扩展 component_type 枚举
backend/tests/agents/nodes/test_technical_pulse_math.py   单测（仅 _math）
backend/tests/fixtures/ohlcv_*.json                测试 fixture
docs/nodes/13-technical-pulse.md                   节点合同文档
```

### 4.3 数据契约

`models/agent_state.py` 新增（建议放进 `AnalysisState.pulse: TechnicalPulse | None`）：

```python
from typing import Literal
from pydantic import BaseModel

class OHLCV(BaseModel):
    date: str   # ISO YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int

class TechnicalIndicator(BaseModel):
    id: Literal["rsi", "macd", "ma_stack", "wk52"]
    label: str        # "RSI 14"
    value: str        # "62" / "+0.42" / "20 > 50 > 200" / "89%"
    sub_label: str    # "Bullish · neutral zone"
    tone: Literal["bull", "bear", "neutral", "warning"]

class TechnicalSignal(BaseModel):
    id: str           # "golden_cross"
    label: str        # "Golden cross"
    direction: Literal["bull", "bear"]
    weight: float
    detail: str | None = None  # 鼠标悬停解释

class MarketContext(BaseModel):
    spy_change_pct: float | None
    vix: float | None
    treasury_10y_pct: float | None
    dxy: float | None
    sector_etf_symbol: str       # "XLK"
    sector_change_pct: float | None

class SentimentSignals(BaseModel):
    fear_greed_value: int | None        # 0-100
    fear_greed_label: str | None        # "Greed"
    put_call_ratio: float | None
    insider_net_usd_90d: float | None   # +12_000_000
    short_interest_pct: float | None    # 2.1
    aaii_bull_minus_bear: float | None  # +8.2

class TechnicalPulse(BaseModel):
    composite_score: int                                   # 0-100
    signal_label: Literal[
        "Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"
    ]
    bull_signal_count: int
    bear_signal_count: int
    bullish_pct: float                                     # 0.0–1.0

    indicators: list[TechnicalIndicator]                   # 长度 4
    active_signals: list[TechnicalSignal]                  # 触发的全部
    market_context: MarketContext
    sentiment: SentimentSignals
    ohlcv: list[OHLCV]                                     # 1Y daily, ~252 点
    ohlcv_ma20: list[float | None]                         # 与 ohlcv 同长度，前 19 个 None
```

### 4.4 信号规则全表

数据：`closes`, `highs`, `lows`, `volumes`（最近 1Y daily）；`spy_closes`（同期 SPY）。
所有信号在 `_technical_pulse_math.py::detect_signals(...)` 内判定，返回 `list[TechnicalSignal]`。

#### Bull（8 条）

| ID | 阈值 | 权重 |
|---|---|---|
| `golden_cross` | `MA50[t-1] ≤ MA200[t-1]` 且 `MA50[t] > MA200[t]`，发生在最近 5 个交易日内 | 1.5 |
| `macd_bullish_crossover` | `MACD[t-1] ≤ signal[t-1]` 且 `MACD[t] > signal[t]`，最近 5 日内（参数 12/26/9） | 1.0 |
| `higher_highs_lows` | `max(close[-20:]) > max(close[-40:-20])` 且 `min(close[-20:]) > min(close[-40:-20])` | 1.2 |
| `volume_confirms_trend` | 最近 30 日：上涨日均成交量 > 1.1 × 下跌日均成交量 | 0.8 |
| `above_all_mas` | `close[t] > MA20[t] > MA50[t] > MA200[t]` | 1.5 |
| `relative_strength` | 30 日相对 SPY：`close[t]/close[t-30] − 1 > spy_close[t]/spy_close[t-30] − 1` | 1.0 |
| `breakout_base` | `close[t] > max(high[-60:-1])`（突破前 60 日高点） | 1.2 |
| `above_vwap` | `close[t-i] > VWAP20[t-i]` 对 `i ∈ [0..4]` 全部成立（连续 5 日） | 0.6 |

#### Bear（3 条）

| ID | 阈值 | 权重 |
|---|---|---|
| `rsi_overbought` | `RSI14[t] > 70` | 1.0 |
| `rsi_bearish_divergence` | `close[t] > max(close[-20:-1])` 且 `RSI14[t] < max(RSI14[-20:-1])` | 1.5 |
| `distribution_days` | 30 日内分布日数 ≥ 4。分布日定义：`close_d < close_{d-1}` 且 `vol_d > 1.25 × avg(vol[-30:])` | 0.8 |

权重表写死在 `_technical_pulse_math.py::SIGNAL_WEIGHTS`，作为 v1 常量。后续调权 = 升 v2 函数版本。

### 4.5 综合评分

```python
import math

def composite_score(signals: list[TechnicalSignal]) -> int:
    """加权信号求和 → tanh 归一到 0-100。中性 = 50。"""
    delta = sum(
        s.weight if s.direction == "bull" else -s.weight
        for s in signals
    )
    # tanh(delta/4) 映射 (-∞, +∞) → (-1, 1)，scale=4 让 ±8 大致饱和
    score = 50 + 50 * math.tanh(delta / 4.0)
    return round(score)


def signal_label(score: int) -> str:
    if score < 30:  return "Strong Sell"
    if score < 45:  return "Sell"
    if score < 55:  return "Neutral"
    if score < 70:  return "Buy"
    return "Strong Buy"
```

`bullish_pct` 定义：`bull_weighted_sum / (bull_weighted_sum + bear_weighted_sum)`，用于 hero 多空力量条。

### 4.6 数据源（FMP + Finnhub）

| 字段 | 来源 | 备注 |
|---|---|---|
| OHLCV 1Y | FMP `/v3/historical-price-full/{ticker}?serietype=line&timeseries=252` | 主数据，必须成功 |
| SPY OHLCV | 同上 ticker=SPY | 算 relative_strength 用 |
| RSI / MACD / MA | **本地计算**（pandas-ta 或手写），不走 FMP technical endpoint | 减少 API 依赖、可单测 |
| VIX / 10Y / DXY | FMP `/v3/quote/^VIX,^TNX,DXY` | 缺失 → None，不阻断 |
| 板块 ETF | 根据 SIC code 映射到 11 个 SPDR ETF（XLK/XLF/XLE...）`/v3/quote/{etf}` | 映射表见 `services/data/sector_map.py` |
| Insider 90d | Finnhub `/stock/insider-transactions?symbol={ticker}&from={today-90d}` | 聚合 net USD |
| Put/Call | FMP options chain（如不可用则 None）| 可选 |
| Short interest | FMP `/v4/short_interest/{ticker}` | 可选 |
| Fear & Greed | `https://production.dataviz.cnn.io/index/fearandgreed/graphdata` | 非官方但稳定多年；CC 实施时验证可达性 |
| AAII bull-bear | v1 **暂不接**——返回 None。需注册 AAII 账号 | 留 TODO，v1.1 再补 |

### 4.7 优雅降级（沿用项目约定）

- `AQ_FMP_API_KEY` 缺失 → 整个 `technical_pulse` 节点直接 emit `step_complete(skipped=True)` 并 return；后续节点正常
- OHLCV 拉取失败 → 同上 skip 整个节点（无主数据无法做任何事）
- 任何**子查询**失败（VIX 拉不到、F&G API 挂了）→ `ErrorEvent(recoverable=True)` + 对应字段置 None，节点继续
- Finnhub key 缺 → insider 字段 None，其余正常

### 4.8 Provider 限流缓冲（v0.11 实施）

FMP 免费档每天 250 calls 易耗。`technicals_data.py` 顶部装饰器 `@_cached(ttl=300s)` 应用到所有 4 个 fetcher，按非 httpx-client args 建 key、失败值不缓存。

效果（同 IP 5 min 内）：
- **同 ticker 重新分析**：FMP 调用 7→0，所有数据命中缓存
- **不同 ticker**：FMP 调用 7→3，仅 ticker 自身 history + sector ETF quote + insider 不命中
- **冷启动**：保持 7 个 FMP 调用

实现细节见 `docs/nodes/13-technical-pulse.md#ttl-缓存`。生产环境想跨 worker 共享需上 Redis（v0.11 不需）。

### 4.9 Pro 钩子（v1 占位、v1.1 实施）

不在 v1 实现，但为前端组件 props 留 schema：

```python
# v1.1 新增 component_type
"pulse_score_explainer_locked_card"   # LLM 一句话解释为什么 Bullish
"insider_detail_locked_card"           # 详细 insider 列表（人名、日期、股数）
```

按现有 `_pro_gate.is_pro_user(state)` short-circuit 模式实现。Free 用户看到 locked 预览卡。

---

## 5. 前端实现

### 5.1 component-registry 注册

`frontend/src/components/component-registry.ts` 增加：

```ts
'pulse_score_hero':      () => import('./pulse/pulse-score-hero'),
'price_chart_card':      () => import('./pulse/price-chart-card'),
'indicator_grid_card':   () => import('./pulse/indicator-grid-card'),
'signal_chips_card':     () => import('./pulse/signal-chips-card'),
'market_context_card':   () => import('./pulse/market-context-card'),
'sentiment_pulse_card':  () => import('./pulse/sentiment-pulse-card'),
```

### 5.2 tab-groups 单一来源

`frontend/src/components/canvas/tab-groups.ts`：

```ts
export const TAB_GROUPS = {
  // ...
  pulse: [
    'pulse_score_hero',
    'price_chart_card',
    'indicator_grid_card',
    'signal_chips_card',
    'market_context_card',
    'sentiment_pulse_card',
  ],
};

export const TAB_ORDER = [
  'verdict', 'valuation', 'strategy', 'risks', 'pulse', 'sources'
] as const;
```

### 5.3 K 线图集成（lightweight-charts）

```bash
# PowerShell, 在 frontend/ 目录下
npm install lightweight-charts
```

`price-chart-card.tsx` 关键约束：

- **必须 dynamic import + ssr: false**（Next.js 16 App Router；该库依赖 `window`）
  ```tsx
  const ChartImpl = dynamic(() => import('./price-chart-impl'), { ssr: false });
  ```
- 用 `useRef` + `useEffect` 创建 chart 实例，**unmount 时调用 `chart.remove()`**，否则 leak
- 3M / 6M / 1Y 切换：**不重建 chart**，调用 `timeScale.setVisibleRange({ from, to })`，从 props.ohlcv 切片
- 暗色 layout 配置：

  ```ts
  const chart = createChart(container, {
    layout: {
      background: { color: 'transparent' },
      textColor: 'rgb(161 161 170)',  // zinc-400
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.04)' },
      horzLines: { color: 'rgba(255,255,255,0.04)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: false },
  });

  chart.addCandlestickSeries({
    upColor: '#10b981',          // emerald-500
    downColor: '#ef4444',        // rose-500
    borderVisible: false,
    wickUpColor: '#10b981',
    wickDownColor: '#ef4444',
  });
  ```
- MA20 用 `addLineSeries({ color: '#a78bfa', lineWidth: 1.5 })`（violet-400）
- 成交量 `addHistogramSeries`，绑定到独立 priceScale（priceScaleId: ''）

### 5.4 视觉规范（"币圈达成看板"具象化）

#### 配色（Tailwind 类名直用）

| 语义 | 文本 | 背景 | 边框 |
|---|---|---|---|
| Bull | `text-emerald-400` | `bg-emerald-500/10` | `border-emerald-500/30` |
| Bear | `text-rose-400` | `bg-rose-500/10` | `border-rose-500/30` |
| Neutral | `text-zinc-400` | `bg-zinc-500/10` | `border-zinc-700` |
| Warning | `text-amber-400` | `bg-amber-500/10` | `border-amber-500/30` |
| Pro 锁 | `text-amber-400` | `bg-amber-500/5` | dashed `border-amber-500/40` |

#### Neon glow（克制使用）

只用在 3 处焦点元素：综合评分大数字、F&G gauge 指针端点、active signal chips 的 hover 态。

```css
/* 评分数字 */
.pulse-score-glow {
  filter: drop-shadow(0 0 16px rgb(16 185 129 / 0.45));
}
/* bear 时切到 rose */
.pulse-score-glow-bear {
  filter: drop-shadow(0 0 16px rgb(244 63 94 / 0.45));
}
```

#### 字体

- 数字：`font-mono tabular-nums`（项目已有 JetBrains Mono）
- 大写小标签：`uppercase tracking-wider text-xs text-zinc-500`
- 评分大数字：`text-7xl font-medium tabular-nums`

#### 动效（framer-motion）

- 评分入场：`initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }}`，spring `{ stiffness: 200, damping: 18 }`
- Signal chips：parent `staggerChildren: 0.04`，child `initial={{ opacity: 0, y: 6 }}`
- F&G gauge 指针：`<motion.path>` 配 `transition={{ type: 'spring', stiffness: 60, damping: 14 }}`，从 0 弹到目标值
- 多空力量条：宽度过渡 600ms ease-out

#### F&G 仪表盘

半圆 SVG，渐变色 stop（red 0% → amber 50% → green 100%），白色指针 + glow 端点。**不要**用纯单色——多段渐变是这个组件的核心视觉。具体几何同 mockup（半径 80，从 (20,100) 到 (180,100)）。

### 5.5 Hero 派生（`deriveHero`）

不修改。Pulse 不抢 Verdict 的 hero——hero 仍然按 `investment_thesis_card.recommendation` → `strategy_dashboard.signal` 顺序派生。Pulse 的 composite_score 仅展示在 Pulse tab 内部的 hero 区。

---

## 6. 测试要求

按项目"节点纯/不纯拆分"约定，**仅** `_technical_pulse_math.py` 写单测。主节点（含 I/O）不写。

`tests/agents/nodes/test_technical_pulse_math.py` 必须覆盖：

- `test_composite_score_neutral_baseline` —— 空 signals 列表 → score == 50
- `test_composite_score_strong_bullish` —— 全 8 条 bull 信号 → score ≥ 90
- `test_composite_score_strong_bearish` —— 全 3 条 bear 信号 → score ≤ 25
- `test_signal_label_thresholds` —— 边界值 29/30/44/45/54/55/69/70 一一映射
- `test_signal_golden_cross_detection` —— fixture: MA50/MA200 在 t-2 交叉 → 命中
- `test_signal_macd_crossover_window` —— 7 天前交叉 → 不命中（5 日窗口）
- `test_signal_rsi_bearish_divergence` —— price 创新高、RSI 走低 → 命中
- `test_signal_distribution_days_count` —— fixture 含 5 个 distribution day → 命中（≥4）
- `test_relative_strength_vs_spy` —— ticker 30 日 +5%、SPY +3% → 命中
- `test_above_vwap_requires_5_consecutive_days` —— 4 日满足、1 日跌破 → 不命中

Fixture 放 `tests/fixtures/ohlcv_*.json`，覆盖 bull/bear/sideways 三种典型形态。

```powershell
# 验证命令（PowerShell, cwd=backend, venv 已激活）
pytest -q tests/agents/nodes/test_technical_pulse_math.py
```

---

## 7. 文档更新

- `CHANGELOG.md` —— 新增 v0.11 条目，列出本次新增/修改的所有文件
- `docs/nodes/13-technical-pulse.md` —— 节点输入/输出/失败模式（参照 `docs/nodes/01-fetch-sec-data.md` 风格）
- `docs/decisions/010-pulse-tab.md` —— 本文件
- `frontend/AGENTS.md` —— 增加章节："使用 lightweight-charts 时必须 dynamic import + ssr: false，否则 Next.js 16 build 会失败（依赖 window）"
- `ARCHITECTURE.md` —— 12 节点流水线图升级为 13 节点，§5 更新

---

## 8. 验收清单

- [ ] `pytest -q tests/agents/nodes/test_technical_pulse_math.py` 全绿
- [ ] `pytest -q` 整体回归全绿（不应破坏现有节点）
- [ ] `cd frontend; npx tsc --noEmit` 通过
- [ ] Free 用户跑 `/api/analyze` 看到完整 Pulse tab
- [ ] `Invoke-RestMethod -Uri http://localhost:8000/api/admin/usage` 显示该次分析 LLM 调用数 = 全局基线（说明 Pulse 没新增 LLM 消耗）
- [ ] 拔掉 `AQ_FMP_API_KEY` 重跑：Pulse tab 不出现，但其他 tab 正常
- [ ] 拔掉 `AQ_FINNHUB_API_KEY` 重跑：Pulse tab 出现，sentiment.insider_net_usd_90d == None
- [ ] K 线图切换 3M/6M/1Y 网络面板**没有新请求**（验证纯前端切片）
- [ ] Verdict tab Hero 不变（`deriveHero` 优先级未受影响）
- [ ] Mobile 视口 (≤640px)：4 列指标网格折成 2 列；Market context 5 项折成 2 列网格
- [ ] 暗色主题下 K 线 candlestick / MA / volume 三层都可读
- [ ] F&G gauge 指针有 spring 入场动画，渐变色 arc 完整渲染

---

## 9. 不在范围内（v1.1+）

- 实时 WebSocket 价格推送（讨论时已否决方案 C）
- LLM 解读综合评分（Pro 钩子占位）
- Insider 详细列表（Pro 钩子占位）
- AAII 数据自动拉取（v1 返回 None）
- 行业横向比较（"和同行业 5 家公司技术面对比"）
- 用户自定义信号权重 / 自定义指标
- Pulse 数据进 `saved_theses` 快照（v1 不存，每次重跑）

---

## 10. CC 实施顺序建议

1. 先 `_technical_pulse_math.py` + 单测 → 全绿后再写主节点
2. 主节点 + `services/data/technicals.py` → 用 `httpx` 同步调用 FMP/Finnhub，**不要**异步并发拉（保持简单；总耗时 < 3s 即可）
3. `models/agent_state.py` 加字段，跑一次 `alembic` 检查（如果 AnalysisState 持久化的话；如不持久化跳过）
4. LangGraph 装配 + `value_analyst.py` 接线
5. 前端 6 个组件，建议顺序：`pulse-score-hero` → `price-chart-card`（最复杂）→ `indicator-grid-card` → `signal-chips-card` → `market-context-card` → `sentiment-pulse-card`
6. 注册 component-registry + tab-groups
7. 跑端到端：起后端 + 前端，分析 NVDA / AAPL 验证视觉
8. 跑验收清单
9. 写 CHANGELOG / docs/nodes/13 / 更新 ARCHITECTURE
