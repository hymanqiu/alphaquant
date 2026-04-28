# Node 11: moat_analysis 🔒 Pro

> 图位置: `risk_yoy_diff → moat_analysis → investment_thesis`

## 职责

按 Hamilton Helmer 「**7 Powers**」框架（Scale Economies / Network Effects / Counter-Positioning / Switching Costs / Branding / Cornered Resource / Process Power）给公司打分，每维 0-10 + 必须有 10-K Item 1 (Business) 中的逐字引文佐证。**不可核验的 score ≥3 自动 demote 到 0**（保留行结构便于 UI 一致性，但去掉无据宣称）。

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
| `financials.cik` | `int` | ✅ | 拉 10-K Item 1 Business |
| `financials.ticker` | `str` | ✅ | LLM prompt + 日志 |
| `financials.entity_name` | `str` | ✅ | LLM prompt + ComponentEvent |

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
| `moat_result` | `dict \| None` | 7 powers 评分 + classification |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `moat_result` 结构体

> **源码**: `backend/agents/nodes/moat_analysis.py` line 280-296

```python
{
    "ticker": str,
    "filing_date": str,                      # ISO date, e.g. "2025-10-31"
    "accession_number": str,
    "filing_url": str,                       # SEC Archives 直链
    "powers": list[MoatPower],               # 7 条, 一个 power 一行
    "overall_moat_score": float,             # max(verified_scores), 1 位小数
    "moat_classification": "wide" | "narrow" | "none",
    "primary_powers": list[PowerName],       # 最多 3 个 score≥3 的最高分 powers
    "thesis_one_liner": str,                 # 一句话护城河论点
    "demoted_power_count": int,              # 引文核验失败被降到 0 的数量
    "confidence": float,                     # [0, 1]
    "parser_strategy": str,                  # extract_business 用的策略
}
```

**`MoatPower` 子结构** (Pydantic):

```python
{
    "power": "scale_economies|network_effects|counter_positioning|switching_costs|branding|cornered_resource|process_power",
    "score": float,                          # [0, 10], 0 = 无证据 / 已被 demote
    "rationale": str,                        # 1-2 句解释; demoted 时前缀 "[demoted] "
    "evidence_quote": str | None,            # 已逐字核验, ≥40 chars; demoted 或 score<3 时 None
}
```

**`overall_moat_score` 计算规则** (`_verify_and_demote` 后):

```python
overall = max(verified_scores)               # 不是平均；强项决定 moat 强度（Helmer 原话）
classification = "wide"   if overall >= 7
                "narrow" if 4 <= overall < 7
                "none"   if overall < 4
```

### `_verify_and_demote` 行为

| 情况 | 动作 |
|------|------|
| score ≥ 3 且 quote 在 source_text 中 | 保留 score 和 quote |
| score ≥ 3 但 quote 不可核验 | **demote**: score → 0, quote → None, rationale 前缀 `[demoted]` |
| score < 3 (无证据 / 弱) | 保留, quote 可为 None |

`primary_powers` 在 demote 之后**重新计算**（取 verified score≥3 中最高 3 个）。

### AAPL 示例 (实际抓出的真实 filing + LLM 模拟输出)

```json
{
  "moat_result": {
    "ticker": "AAPL",
    "filing_date": "2025-10-31",
    "accession_number": "0000320193-25-000079",
    "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "powers": [
      {
        "power": "branding",
        "score": 9.0,
        "rationale": "Apple brand commands premium pricing across multiple categories with sustained gross margin above industry average.",
        "evidence_quote": "The Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories, and sells a variety of related services."
      },
      {
        "power": "switching_costs",
        "score": 7.5,
        "rationale": "Tightly integrated ecosystem (iCloud, iMessage, Health) creates real friction for users to leave.",
        "evidence_quote": "..."
      },
      {"power": "scale_economies", "score": 6.0, "rationale": "...", "evidence_quote": "..."},
      {"power": "network_effects", "score": 5.0, "rationale": "...", "evidence_quote": "..."},
      {"power": "process_power", "score": 4.0, "rationale": "...", "evidence_quote": "..."},
      {"power": "cornered_resource", "score": 2.0, "rationale": "No specific evidence.", "evidence_quote": null},
      {"power": "counter_positioning", "score": 1.0, "rationale": "Not a counter-positioned business.", "evidence_quote": null}
    ],
    "overall_moat_score": 9.0,
    "moat_classification": "wide",
    "primary_powers": ["branding", "switching_costs", "scale_economies"],
    "thesis_one_liner": "Apple's dominant brand power, reinforced by ecosystem switching costs, defines a wide and durable moat.",
    "demoted_power_count": 0,
    "confidence": 0.78,
    "parser_strategy": "strict_multi_ws"
  }
}
```

## 核心算法

```
1. is_pro_user(state) → False → emit moat_locked_card → return None
2. is_llm_configured() → False → emit skipped → return None

3. sec_client.fetch_10k(cik, n_back=0)
   └── 通常命中缓存（qualitative_analysis 已暖过）

4. extract_business(html) — Item 1 Business 段
   └── 三层正则回退 (strict_multi_ws → loose → fallback)
   └── 失败 → emit skipped → return None

5. smart_truncate(text, 12_000) — 头 6K + 尾 6K + 中间标记

6. LLMClient.complete_json("moat_analysis", response_model=MoatInsight)
   └── 失败 → emit skipped → return None

7. _verify_and_demote(insight.powers, source_text=section.text)
   └── score ≥ 3 + quote 不可核验 → demote 到 0; rationale 加 [demoted]
   └── score < 3 → 原样保留

8. 用 verified_scores 重新计算 overall_moat_score = max(scores)
9. 用 verified_scores 重新计算 primary_powers (top 3 of score ≥ 3)
10. emit ComponentEvent("moat_analysis_card")
```

## 关键假设

- **Helmer 的核心观点**：moat 强度由最强那个 power 决定（不是 7 个的平均），所以用 `max()` 而非平均
- 大多数公司在大多数 power 上得分应该是 0-3（"absent" / "weak"）—— 7+ 的得分需要结构性证据
- Item 1 Business 比 MD&A 更适合 moat 分析（业务模型 / 竞争定位 / 客户结构都在这里）
- 12K 头尾截断保留 Company Background + Strategy / Distribution 部分（XBRL 已捕获财务，不需要重复）
- LLM 容易在 "branding" / "network_effects" 上虚高 —— demote 机制是必要的
- 同一份 10-K 一年内 moat 评分应该稳定（缓存命中后零额外 LLM 成本）

## LLM 使用

| 调用 | task_tag | Prompt | 输入 | 输出 |
|------|----------|--------|------|------|
| 7 Powers 评分 | `moat` | `prompts/moat_analysis_v1.yaml` | ticker + company_name + filing_date + accession + 12K Business 文本 | `MoatInsight` (Pydantic) |

**单次成本**: ~3K input + ~1.5K output = **~$0.001 DeepSeek / ~$0.025 GPT-4o**。

## 失败模式与降级

| 条件 | 行为 |
|------|------|
| `user_tier="free"` | emit `moat_locked_card`, 返回 None |
| `financials.cik` 缺失 | emit skipped, 返回 None |
| LLM 未配置 | emit skipped, 返回 None |
| `fetch_10k` 失败 | emit skipped, 返回 None |
| `extract_business` 解析失败 (Item 1 找不到 / 太短) | emit skipped, 返回 None |
| LLM 调用失败 | emit skipped, 返回 None |
| LLM 输出引文不可核验 | 单条 power demote 到 0, 其它 power 不受影响 |
| 全部 7 个 power 都 < 3 | 正常输出, classification="none", primary_powers=[] |
| **下游影响** | `investment_thesis` 仍能跑；`moat_summary` 显示 "not available" |

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/moat_analysis.py` | 节点入口 + MoatPower/MoatInsight Pydantic + `_verify_and_demote` |
| `backend/agents/nodes/_pro_gate.py` | tier 门控 helper |
| `backend/agents/nodes/qualitative_analysis.py` | 共用 `_normalize` (smart-quote / 空白归一化) |
| `backend/services/tenk_parser.py` | `extract_business` (3 层正则) + `smart_truncate` |
| `backend/services/sec_client.py` | `fetch_10k(cik, n_back=0)` + 缓存 |
| `backend/prompts/moat_analysis_v1.yaml` | 7 Powers 评分 prompt |

## 与其他节点的关系

- **依赖**: `fetch_sec_data` (cik); `qualitative_analysis` 不是硬依赖但已经把当年 10-K HTML 暖进缓存
- **消费者**: `investment_thesis` 通过 `_moat_summary()` 把 classification + primary_powers + thesis_one_liner 写入 thesis prompt

## 前端组件

| component_type | 组件 | 触发条件 |
|----------------|------|----------|
| `moat_analysis_card` | `MoatAnalysisCard` — 7 power 渐变进度条 + primary badge + verbatim 引文 + overall = max | 节点成功输出 |
| `moat_locked_card` | `ProLockedCard` (shared) — Pro 升级 CTA | `user_tier="free"` |

## 相关 ADR

- [009 — tier-gating-strategy](../decisions/009-tier-gating-strategy.md)
- [006 — unified-llm-client](../decisions/006-unified-llm-client.md)
