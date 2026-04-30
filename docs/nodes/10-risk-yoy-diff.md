# Node 10: risk_yoy_diff 🔒 Pro

> 图位置: `qualitative_analysis → risk_yoy_diff → moat_analysis`

## 职责

抓**当年 + 上一年**两份 10-K 的 Item 1A Risk Factors，让 LLM 做 4 桶 YoY diff：新增风险 / 删除风险 / 加重风险 / 减轻风险。每条变化必须有**来自正确年份**的逐字引文支撑，否则丢弃。这是少数能反映管理层风险态度变化的客观信号。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |
| `user_tier` | `str` | ✅ | `"free"` 短路 emit locked card |

### 子字段访问

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.cik` | `int` | ✅ | 拉两年 10-K 的索引 |
| `financials.ticker` | `str` | ✅ | LLM prompt + 日志 |
| `financials.entity_name` | `str` | ✅ | LLM prompt |

不依赖 `qualitative_result` —— 重新独立解析两年 RF，避免错过去年数据。

### AAPL 示例 (输入子字段)

```json
{
  "user_tier": "pro",
  "financials": {"ticker": "AAPL", "entity_name": "Apple Inc.", "cik": 320193}
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `risk_yoy_diff_result` | `dict \| None` | 4 桶 diff 结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `risk_yoy_diff_result` 结构体

> **源码**: `backend/agents/nodes/risk_yoy_diff.py` line 252-279

```python
{
    "ticker": str,
    "current_filing": {
        "filing_date": str,                    # ISO date
        "accession_number": str,
        "url": str,                            # SEC Archives 直链
    },
    "prior_filing": {
        "filing_date": str,
        "accession_number": str,
        "url": str,
    },
    "summary": str,                            # 2-3 句年度风险态度总结
    "new_risks":          list[RiskChange],    # ↓ 见下, 最多 4 条
    "removed_risks":      list[RiskChange],
    "escalated_risks":    list[RiskChange],
    "de_escalated_risks": list[RiskChange],
    "rejected_change_count": int,              # 引文核验未通过被丢弃总数
    "confidence": float,                       # [0, 1]
}
```

**`RiskChange` 子结构** (Pydantic):

```python
{
    "kind": "new" | "removed" | "escalated" | "de_escalated",
    "category": "regulatory|competitive|operational|financial|macro|technology|legal|concentration",
    "title": str,                              # 5-12 词总结
    "description": str,                        # 1-2 句解释
    "quote_current": str | None,               # 当年 RF 中的逐字引文 (≥40 chars)
    "quote_prior":   str | None,               # 上年 RF 中的逐字引文 (≥40 chars)
}
```

**核验规则** (`_verify_change` in `risk_yoy_diff.py`):

| kind | quote_current 要求 | quote_prior 要求 |
|------|:--:|:--:|
| `new` | ✅ 必须验证通过 | (忽略) |
| `removed` | (忽略) | ✅ 必须验证通过 |
| `escalated` | ✅ 必须验证通过 | ✅ 必须验证通过 |
| `de_escalated` | ✅ 必须验证通过 | ✅ 必须验证通过 |

任一必需引文未通过 → 整条 RiskChange 丢弃。

### AAPL 示例 (实际抓出的真实 filings + LLM 模拟输出)

```json
{
  "risk_yoy_diff_result": {
    "ticker": "AAPL",
    "current_filing": {
      "filing_date": "2025-10-31",
      "accession_number": "0000320193-25-000079",
      "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
    },
    "prior_filing": {
      "filing_date": "2024-11-01",
      "accession_number": "0000320193-24-000123",
      "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"
    },
    "summary": "Risk posture in 2025 emphasizes regulatory exposure under DMA-style regimes; previously generic risk framing has been replaced by specific antitrust language.",
    "new_risks": [
      {
        "kind": "new",
        "category": "regulatory",
        "title": "DMA enforcement intensifies",
        "description": "EU Digital Markets Act compliance became materially more concrete this year.",
        "quote_current": "The following summarizes factors that could have a material adverse effect on the Company's business, reputation, results of operations, financial condition and stock price.",
        "quote_prior": null
      }
    ],
    "removed_risks": [],
    "escalated_risks": [],
    "de_escalated_risks": [],
    "rejected_change_count": 2,
    "confidence": 0.7
  }
}
```

## 核心算法

```
1. is_pro_user(state) → False → emit risk_yoy_diff_locked_card → return None
2. is_llm_configured() → False → emit skipped → return None

3. 并行 (or 顺序复用 cache):
   ├── current = sec_client.fetch_10k(cik, n_back=0)  → extract_risk_factors
   └── prior   = sec_client.fetch_10k(cik, n_back=1)  → extract_risk_factors

   任一缺失或解析失败 → emit skipped → return None
   (注: current 通常已被 qualitative_analysis 缓存命中, prior 是这里第一次拉)

4. truncate_head(text, 12_000) 各自截到 12K (两段加起来 ~24K input tokens)

5. LLMClient.complete_json("risk_yoy_diff", response_model=RiskYoYDiff)
   └── 失败 (402 / parse / budget) → emit skipped → return None

6. 4 桶分别过 _filter_changes(items, current_text, prior_text):
   ├── 每条 RiskChange 用 _verify_change(...) 检查必需引文
   └── 不通过的整条丢弃, 累加 rejected_change_count

7. 组装结果, emit ComponentEvent("risk_yoy_diff_card")
```

## 关键假设

- 公司每年的 Risk Factors 节是同一拨律师写的，**真实变化 = 法律视角认为值得专门改的**
- "新增风险" 比 "加重风险" 信号更强（管理层不会无故加新风险段落）
- 同一引文出现在两年都是常态（boilerplate），LLM 应该忽略这类
- prior year 解析失败的概率比 current 高（旧格式可能不同），需要降级容忍
- 截到 12K 字符够覆盖 head 部分（按重要性排序）

## LLM 使用

| 调用 | task_tag | Prompt | 输入 | 输出 |
|------|----------|--------|------|------|
| YoY diff | `risk_yoy_diff` | `prompts/risk_yoy_diff_v1.yaml` | ticker + company_name + 当年/上年 filing meta + 12K + 12K Risk Factors 文本 | `RiskYoYDiff` (Pydantic, 4 桶 + summary + confidence) |

**单次成本**: ~24K input + ~1.5K output = **~$0.0035 DeepSeek / ~$0.10 GPT-4o**（管线最贵的单次调用）。

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| `user_tier="free"` | emit `risk_yoy_diff_locked_card`, 返回 None |
| `financials.cik` 缺失 | emit skipped, 返回 None |
| LLM 未配置 | emit skipped, 返回 None |
| current 或 prior 任一 fetch_10k 失败 | emit skipped, 返回 None |
| 两年 Risk Factors 任一解析失败 | emit skipped, 返回 None |
| 公司只有一份 10-K (新上市) | n_back=1 找不到 → emit skipped |
| LLM 调用失败 | emit skipped, 返回 None |
| LLM 输出引文不在源文本中 | 整条 RiskChange 丢弃, 其它继续 |
| 4 桶全空 | 仍 emit ComponentEvent (前端显示 "no material changes") |
| **下游影响** | `investment_thesis` 仍能跑；`risk_yoy_summary` 显示 "not available" |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/risk_yoy_diff.py` | 节点入口 + RiskChange/RiskYoYDiff Pydantic + `_verify_change` / `_filter_changes` |
| `backend/agents/nodes/_pro_gate.py` | tier 门控 helper |
| `backend/agents/nodes/qualitative_analysis.py` | 共用 `_normalize` 和 `verify_quotes` |
| `backend/services/tenk_parser.py` | `extract_risk_factors` / `truncate_head` |
| `backend/services/sec_client.py` | `fetch_10k(cik, n_back=0)` + `fetch_10k(cik, n_back=1)` (共享 6-entry FIFO HTML 缓存) |
| `backend/prompts/risk_yoy_diff_v1.yaml` | YoY diff prompt |

## 与其他节点的关系

- **依赖**: `fetch_sec_data` (cik); `qualitative_analysis` 不是硬依赖但顺序在前 (帮忙暖了 current 10-K HTML 缓存)
- **消费者**: `investment_thesis` 通过 `_risk_yoy_summary()` 把 4 桶 diff 写入 thesis prompt

## 前端组件

| component_type | 组件 | 触发条件 |
|----------------|------|----------|
| `risk_yoy_diff_card` | `RiskYoYDiffCard` — 4 桶 2x2 网格；escalated/de_escalated 显示 prior↔current 并排引文；底部双年 SEC 链接 | 节点成功输出（即使 4 桶都空） |
| `risk_yoy_diff_locked_card` | `ProLockedCard` (shared) — Pro 升级 CTA | `user_tier="free"` |

## 相关 ADR

- [009 — tier-gating-strategy](../decisions/009-tier-gating-strategy.md)
- [006 — unified-llm-client](../decisions/006-unified-llm-client.md)
