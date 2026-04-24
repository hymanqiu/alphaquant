# Node 5: event_sentiment

> 图位置: `relative_valuation → event_sentiment → event_impact`

## 职责

从 Finnhub 获取公司新闻和内部人情绪数据，使用 LLM 分析新闻情绪，计算综合情绪评分和安全边际修正量。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.ticker` | `str` | ✅ | Finnhub API + CIK 解析参数 |

> 注意: 仅使用 `ticker`，不直接访问财务数据。CIK 通过 `ticker_resolver.resolve(ticker)` 获取。

### NVDA 示例 (输入)

```json
{ "financials": { "ticker": "NVDA" } }
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_sentiment_result` | `dict \| None` | 情绪分析结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `event_sentiment_result` 结构体

> **源码**: `backend/agents/nodes/event_sentiment.py` line 366-379

```python
{
    "ticker": str,
    "overall_sentiment": float,                    # [-1, 1], 综合情绪
    "sentiment_label": str,                        # "Very Bearish" / "Bearish" / "Neutral" / "Bullish" / "Very Bullish"
    "news_score": float | None,                    # [-1, 1], LLM/Finhub 新闻情绪
    "insider_score": float | None,                 # [-1, 1], 内部人情绪
    "insider_mspr": float | None,                  # Monthly Share Purchase Ratio
    "insider_net_change": int | None,              # 内部人净交易股数
    "sentiment_adjustment": {
        "margin_of_safety_pct_delta": int,         # MoS 修正量 (%)
        "reasoning": str,                          # 修正理由
    },
    "articles": [                                  # 已分类文章列表 (最多 20 篇 + 8-K)
        {
            "headline": str,
            "source": str,
            "url": str,
            "date": str | int,                     # datetime 原始值 (str 或 unix timestamp)
            "sentiment": float,                    # [-1, 1]
            "event_type": str,                     # "earnings"|"guidance"|"ma"|"regulatory"|...
            "confidence": float,                   # [0, 1]
            "is_sec_filing": bool,
        },
    ],
    "article_count": int,                          # 总文章数 (含 8-K)
    "llm_summary": str | None,                     # LLM 总结
    "key_events": list[str],                       # LLM 提取的关键事件 (无 LLM 时为 [])
}
```

### 情绪判定阈值

| `overall_sentiment` 范围 | `sentiment_label` | `margin_of_safety_pct_delta` |
|:---:|---|:---:|
| < -0.5 | Very Bearish | -8% |
| < -0.2 | Bearish | -4% |
| -0.2 ~ 0.2 | Neutral | 0% |
| > 0.2 | Bullish | +3% |
| > 0.5 | Very Bullish | +5% |

> **权重**: news_score × 60% + insider_score × 40% (两者都有时)。
> **不对称设计**: 负面惩罚 (-8%) 大于正面奖励 (+5%)，保守原则。

### NVDA 示例 (输出)

```json
{
  "event_sentiment_result": {
    "ticker": "NVDA",
    "overall_sentiment": 0.35,
    "sentiment_label": "Bullish",
    "news_score": 0.42,
    "insider_score": 0.22,
    "insider_mspr": 0.22,
    "insider_net_change": 15000,
    "sentiment_adjustment": {
      "margin_of_safety_pct_delta": 3,
      "reasoning": "Bullish sentiment — lowering margin-of-safety bar by 3%"
    },
    "articles": [
      {
        "headline": "NVIDIA Reports Record Revenue of $60.9 Billion in FY2024",
        "source": "SEC EDGAR",
        "url": "https://www.sec.gov/...",
        "date": "2024-02-28",
        "sentiment": 0.85,
        "event_type": "earnings",
        "confidence": 0.9,
        "is_sec_filing": true
      },
      {
        "headline": "NVIDIA unveils next-gen Blackwell GPU architecture",
        "source": "Reuters",
        "url": "https://...",
        "date": "2024-03-18",
        "sentiment": 0.7,
        "event_type": "product",
        "confidence": 0.8,
        "is_sec_filing": false
      }
    ],
    "article_count": 15,
    "llm_summary": "NVDA shows strong positive momentum driven by AI demand and record earnings...",
    "key_events": ["Record FY2024 revenue", "Blackwell GPU launch", "AI datacenter demand surge"]
  },
  "reasoning_steps": [
    "Fetched 87 news articles (last 30 days)",
    "Filtered out 52 irrelevant articles, kept 35 relevant",
    "Found 2 SEC 8-K filings (last 30 days)",
    "LLM sentiment analysis: overall score 0.42",
    "Insider sentiment: MSPR=0.22, net share change=15000",
    "Overall sentiment: Bullish (score: 0.35)",
    "Sentiment MoS adjustment: +3%"
  ]
}
```

## 核心算法

```
1. 获取新闻: finnhub_client.get_company_news(ticker, days=30)
   └── 分 7 天批次并发 (semaphore=3), 按 id 去重, 按 datetime DESC 排序

2. 相关度过滤 (event_sentiment_math.py):
   ├── 评分: 4(标题含ticker) 3(summary+related) 2(仅related) 0(排除)
   ├── TICKER_ALIASES 公司名匹配 (38 公司)
   └── 最多保留 30 篇

2b. 权威来源过滤 (event_sentiment_math.py):
   ├── AUTHORITATIVE_SOURCES 白名单 (Reuters/Bloomberg/WSJ 等 24 个)
   ├── SEC 8-K 文件始终保留
   └── 全部过滤掉时退回原始列表 (graceful degradation)

3. SEC 8-K 文件: sec_client.get_recent_8k_filings(cik, days=30)
   └── 预置到文章列表 (视为权威)

4. LLM 情绪分析 (DeepSeek):
   ├── analyze_news_sentiment(ticker, articles[:20])
   ├── XML 标签 <articles> 包裹 (防 prompt injection)
   └── _validate_llm_response() 校验: score∈[-1,1], confidence∈[0,1]

5. 内部人情绪: finnhub_client.get_insider_sentiment(ticker, months=3)
   └── MSPR + net change

6. 综合评分:
   ├── 60% 新闻 + 40% 内部人 (两者都有时)
   └── 情绪修正: 见上方阈值表
```

## 关键假设

- 新闻权重 60%、内部人 40% 的配比基于经验判断，未经验证
- Finnhub Free plan 情绪 API (news-sentiment) 不可用 (403)，使用 LLM 降级
- 权威来源白名单是手工维护的固定列表
- 30 天新闻窗口是固定值，未按公司调整

## LLM 使用

| 调用 | 模型 | 用途 |
|------|------|------|
| `analyze_news_sentiment()` | DeepSeek (`AQ_LLM_MODEL`) | 批量分析 20 篇新闻的情绪和事件类型 |

LLM 配置: `backend/services/llm_sentiment.py`
- `AQ_LLM_API_KEY`, `AQ_LLM_BASE_URL`, `AQ_LLM_MODEL`

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| `AQ_FINNHUB_API_KEY` 未设置 | 节点跳过, 不阻塞 |
| Finnhub Free plan (403) | Premium 情绪不可用 → LLM 降级 |
| LLM 不可用 | LLM 返回 None → 仅基于内部人数据 |
| 无新闻 | news_score = None → 仅内部人 |
| 无内部人 | insider_data = None → 仅新闻 |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/event_sentiment.py` | 节点入口 + 编排 |
| `backend/agents/nodes/event_sentiment_math.py` | 纯计算 (过滤/评分/标签) |
| `backend/services/finnhub_client.py` | Finnhub HTTP 客户端 |
| `backend/services/llm_sentiment.py` | LLM 情绪分析 |

## 配置依赖

| 环境变量 | 必需 | 说明 |
|----------|------|------|
| `AQ_FINNHUB_API_KEY` | 可选 | 未设置时节点跳过 |
| `AQ_LLM_API_KEY` | 可选 | LLM 情绪分析 |
| `AQ_LLM_BASE_URL` | 可选 | 默认 DeepSeek |
| `AQ_LLM_MODEL` | 可选 | 默认 `deepseek-chat` |
