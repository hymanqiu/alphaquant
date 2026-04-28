# Node 9: qualitative_analysis 🔒 Pro

> 图位置: `strategy → qualitative_analysis → risk_yoy_diff`

## 职责

拉取最新 10-K 一次，**并行**抽取 Item 7 (MD&A) 和 Item 1A (Risk Factors) 两节文本，分别用 LLM 提炼定性洞察：管理层语气、前瞻指引、增长驱动 / 担忧、风险分类与 Top 5 风险。每条引文必须是源文本的逐字 substring，幻觉引文自动丢弃。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |
| `user_tier` | `str` | ✅ | `"free"` 短路 emit locked card；`"pro"` / `"admin"` 才执行 |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.cik` | `int` | ✅ | 拉取该公司 10-K 的 SEC EDGAR 索引 |
| `financials.ticker` | `str` | ✅ | LLM prompt + 日志 |
| `financials.entity_name` | `str` | ✅ | LLM prompt + ComponentEvent props |

### AAPL 示例 (输入子字段)

```json
{
  "user_tier": "pro",
  "financials": {
    "ticker": "AAPL",
    "entity_name": "Apple Inc.",
    "cik": 320193
  }
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `qualitative_result` | `dict \| None` | 嵌套结构 `{mdna, risk_factors}` (见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `qualitative_result` 结构体

> **源码**: `backend/agents/nodes/qualitative_analysis.py` line 415-442

```python
{
    "ticker": str,
    "filing_date": str,                    # ISO date, e.g. "2025-10-31"
    "accession_number": str,               # e.g. "0000320193-25-000079"
    "filing_url": str,                     # SEC Archives 直链 .htm
    "mdna": dict | None,                   # ↓ 失败时 None
    "risk_factors": dict | None,           # ↓ 失败时 None
}
```

**`mdna` 子结构** (LLM 输出 → Pydantic `MDNAInsight`):

```python
{
    "tone": "optimistic|neutral|cautious|negative",
    "forward_guidance_summary": str,       # 1-3 句前瞻指引
    "growth_drivers": list[str],           # 3-5 条
    "management_concerns": list[str],      # 3-5 条
    "notable_quotes": list[str],           # 已逐字核验, 最多 6 条
    "rejected_quote_count": int,           # 被丢弃的幻觉引文数
    "confidence": float,                   # [0, 1]
    "parser_strategy": str,                # "strict_multi_ws" / "loose_any_ws" / "fallback_loose"
    "parser_version": int,                 # 当前为 1
    "mdna_char_count": int,                # 抽出原文长度
    "llm_sent_char_count": int,            # 实际喂给 LLM 长度 (smart_truncate 后)
}
```

**`risk_factors` 子结构** (Pydantic `RiskFactorInsight`):

```python
{
    "risk_categories": dict[Category, int],  # e.g. {"regulatory": 5, "competitive": 3}
    "top_risks": [
        {
            "category": "regulatory|competitive|operational|financial|macro|technology|legal|concentration",
            "title": str,                  # 4-10 词总结
            "description": str,            # 1-2 句解释
            "severity": "high|medium|low",
            "quote": str,                  # 已逐字核验, ≥40 字符
        },
        ...                                # 最多 5 条
    ],
    "rejected_risk_count": int,            # 被丢弃的不可核验 risk 数
    "concentration_risk": str | None,      # 高度集中风险（客户 / 地区 / 产品）
    "confidence": float,
    "parser_strategy": str,
    "parser_version": int,
    "risk_char_count": int,
    "llm_sent_char_count": int,
}
```

### AAPL 示例 (实际抓出的真实数据 + LLM 模拟输出)

```json
{
  "qualitative_result": {
    "ticker": "AAPL",
    "filing_date": "2025-10-31",
    "accession_number": "0000320193-25-000079",
    "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "mdna": {
      "tone": "cautious",
      "forward_guidance_summary": "Management expects continued macro headwinds offset by Services momentum and installed-base growth.",
      "growth_drivers": ["Services revenue growth across App Store, cloud, and financial services", "Installed-base expansion driving recurring revenue"],
      "management_concerns": ["Foreign-exchange headwinds on international revenue", "Regulatory scrutiny (DMA, antitrust investigations)"],
      "notable_quotes": ["The following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in Part II, Item 8 of this Form 10-K."],
      "rejected_quote_count": 1,
      "confidence": 0.72,
      "parser_strategy": "strict_multi_ws",
      "mdna_char_count": 18020,
      "llm_sent_char_count": 11969
    },
    "risk_factors": {
      "risk_categories": {"regulatory": 5, "competitive": 3, "macro": 4, "concentration": 2},
      "top_risks": [
        {
          "category": "regulatory",
          "title": "DMA / antitrust exposure",
          "description": "Digital Markets Act and ongoing investigations could require material business model changes.",
          "severity": "high",
          "quote": "The following summarizes factors that could have a material adverse effect on the Company's business, reputation, results of operations, financial condition and stock price."
        }
      ],
      "rejected_risk_count": 1,
      "concentration_risk": "Significant component sourcing dependency on limited number of suppliers.",
      "confidence": 0.82,
      "parser_strategy": "strict_multi_ws",
      "risk_char_count": 68047,
      "llm_sent_char_count": 16073
    }
  }
}
```

## 核心算法

```
1. is_pro_user(state) check (_pro_gate.py)
   └── False (free tier) → emit qualitative_locked_card → return None

2. is_llm_configured() check
   └── False → emit skipped event → return None

3. sec_client.fetch_10k(cik, n_back=0)
   └── 命中 6-entry FIFO HTML 缓存？复用，否则 GET /submissions/CIK*.json
       + 下载 primary_document .htm (≤20MB, 否则拒绝)

4. 并行解析 (in-process, no I/O):
   ├── extract_mdna(html)       → ExtractedSection 或 None
   └── extract_risk_factors(html) → ExtractedSection 或 None

   两节都 None → emit skipped → return None
   只有一节解析成功 → 仅跑那一节的 LLM

5. asyncio.gather(_analyze_mdna(...), _analyze_risk_factors(...), return_exceptions=True)
   ├── _analyze_mdna: smart_truncate(text, 12K) → LLMClient.complete_json("mdna_analysis")
   │                  → verify_quotes(notable_quotes, source_text) → 丢弃幻觉
   └── _analyze_risk_factors: truncate_head(text, 16K) → LLMClient.complete_json("risk_factors")
                              → 每条 top_risk 的 quote 用 _verify_risk_quote 核验
                              → 不通过的整条 risk 丢弃

6. 部分成功 OK：成功的那部分 emit ComponentEvent，失败的略过
   ├── mdna 成功 → emit qualitative_insights_card
   └── risk_factors 成功 → emit risk_factors_card

7. 组装嵌套 qualitative_result = {ticker, filing_date, ..., mdna: ..., risk_factors: ...}
```

## 关键假设

- 10-K 一年只更新一次，HTML 内容稳定（缓存命中率高）
- MD&A 结构是「Overview → Results → Liquidity → Critical Accounting」，head + tail 截断保留 LLM 最有用部分（XBRL 已捕获 Results 数值）
- Risk Factors 公司按重要性排序，head-only 截断保留最关键风险
- 幻觉引文是常态，**逐字核验是真正的防线**（system prompt 的指令是辅助）
- 部分成功比整体失败有价值——MD&A 失败但 Risk Factors 成功仍然给用户出半张卡片

## LLM 使用

| 调用 | task_tag | Prompt | 输入 | 输出 |
|------|----------|--------|------|------|
| MD&A 分析 | `mdna` | `prompts/mdna_analysis_v1.yaml` | ticker + company_name + filing_date + accession + 12K MD&A 文本 | `MDNAInsight` |
| Risk Factors 抽取 | `risk_factors` | `prompts/risk_factors_v1.yaml` | ticker + company_name + filing_date + accession + 16K Risk Factors 文本 | `RiskFactorInsight` |

两次调用通过 `asyncio.gather` 并行，节省 ~2s 端到端延迟。

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| `user_tier="free"` | emit `qualitative_locked_card` (Pro 锁定预览), 返回 None |
| `financials.cik` 缺失 | emit skipped, 返回 None |
| LLM 未配置 | emit skipped, 返回 None |
| `fetch_10k` 失败 (网络 / 404 / 非 HTML primary doc) | emit skipped, 返回 None |
| 两节都解析失败 | emit skipped, 返回 None |
| 仅一节解析成功 | 仅跑那一节的 LLM, 另一节 None |
| LLM 调用任一节失败 (402 / parse error / budget exceeded) | 该节 None, 另一节继续 |
| 引文核验失败 | 整条引文 / 整条 risk 丢弃, 不影响其它字段 |
| **下游影响** | `investment_thesis` 仍能跑；缺失字段在 thesis prompt 里显示 "not available" |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/qualitative_analysis.py` | 节点入口 + 并行调度 + Pydantic 模型定义 + 引文核验 |
| `backend/agents/nodes/_pro_gate.py` | tier 门控 helper |
| `backend/services/tenk_parser.py` | `extract_mdna` / `extract_risk_factors` / `smart_truncate` / `truncate_head` |
| `backend/services/sec_client.py` | `fetch_10k(cik, n_back)` + FIFO HTML 缓存 |
| `backend/services/llm/client.py` | `LLMClient.complete_json` 单一入口 |
| `backend/prompts/mdna_analysis_v1.yaml` | MD&A 抽取 prompt |
| `backend/prompts/risk_factors_v1.yaml` | Risk Factors 抽取 prompt |

## 与其他节点的关系

- **依赖**: `fetch_sec_data` (cik); 不依赖 `strategy` 但顺序在它后面 (LangGraph 串行)
- **消费者**: `risk_yoy_diff` 共用 10-K HTML 缓存; `investment_thesis` 通过 `_qualitative_summary()` 读取 `mdna` + `risk_factors` 字段写入 thesis prompt

## 前端组件

| component_type | 组件 | 触发条件 |
|----------------|------|----------|
| `qualitative_insights_card` | `QualitativeInsightsCard` — tone 徽章 + 前瞻指引 + 增长驱动/担忧双栏 + verbatim quotes | mdna 分析成功 |
| `risk_factors_card` | `RiskFactorsCard` — 8 类徽章条 + Top risks 列表 + concentration callout | risk_factors 分析成功 |
| `qualitative_locked_card` | `ProLockedCard` (shared) — Pro 升级 CTA | `user_tier="free"` |

## 相关 ADR

- [009 — tier-gating-strategy](../decisions/009-tier-gating-strategy.md)
- [006 — unified-llm-client](../decisions/006-unified-llm-client.md)
