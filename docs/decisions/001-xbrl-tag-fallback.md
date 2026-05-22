# ADR 001: XBRL Tag Fallback Strategy

**状态**: 已采纳(2025-04 初版方案 C → 2026-05 修订为方案 B + 早 tag winner,见下方"2026-05 修订")
**日期**: 2025-04(初版) · 2026-05(修订,PR #15)
**影响节点**: fetch_sec_data
**相关代码**: `backend/services/sec_agent.py` → `_extract_annual_metrics()`

## 背景

不同公司在 SEC EDGAR 中使用不同的 XBRL 标签表达同一财务概念。例如 NVIDIA 的资本支出：
- 早期使用 `PaymentsToAcquirePropertyPlantAndEquipment`
- 近年改用 `PaymentsToAcquireProductiveAssets`

单一标签匹配会导致：选了旧标签 → 只有历史数据没有最新数据；选了新标签 → 没有历史数据。

## 考虑的方案

### 方案 A: 取第一个匹配的标签
- 简单直接
- 问题：如果第一个标签是旧标签（只有历史数据），最新年份数据缺失
- 问题：标签顺序在不同公司间不稳定

### 方案 B: 取所有候选标签的数据并合并
- 数据最全
- 问题：不同标签的数值可能有口径差异（如含税 vs 不含税收入），合并后数据不一致

### 方案 C: 所有候选都尝试，选择 latest_year 值最大的 ✓(初版采用,2026-05 被方案 B' 取代)
- 优先选择"有最新数据的标签"
- 如果新标签有 2025 数据而旧标签只到 2023，自动选新标签
- 如果旧标签反而更新（如公司回退到旧标签），也能正确选择

## 初版决策 (2025-04)

采用方案 C。在 `_extract_annual_metrics()` 中：
1. 遍历 `TAG_MAP` 中定义的所有候选标签
2. 对每个候选调用 `_extract_for_tag()` 获取年序列
3. 选择 `latest_year` 值最大的那个

## 2026-05 修订:方案 B'(早 tag winner,per-year merge)

### 触发原因

PR #10 引入 `LongTermDebtAndCapitalLeaseObligations`(ASC 842 lease-inclusive 标签)到 `long_term_debt` 候选链后,PR #15 暴露了方案 C 的失败 case:

- **KO(Coca-Cola)**: 新 tag `LongTermDebtAndCapitalLeaseObligations` 仅 2024 一年有值,旧 tag `LongTermDebt` 覆盖 2015–2023。
- 方案 C 选 "latest_year 最大" → 选中新 tag → 历史序列从 9 年塌缩到 1 年。
- 相对估值、DCF 需要完整历史时间序列,这是致命的回归。

### 新策略:per-year merge,早 tag winner

```
for tag in tag_candidates:           # TAG_MAP 排序即优先级,modern tag 在前
    for metric in _extract_for_tag(facts[tag]):
        merged.setdefault(metric.calendar_year, metric)  # 该年没数据才接受
```

- 每个 `calendar_year` 只接受第一个写入它的标签 → **同一年内绝不混标签**
- `TAG_MAP` 中靠前的标签先写入 → modern / lease-inclusive 标签优先
- 后续(legacy)标签**仅**为它没覆盖的年份补值 → 保住深度历史

### 这是不是当年被否决的方案 B?

是,但加了一条关键约束。原方案 B 的否决理由是:

> "不同标签的数值可能有口径差异（如含税 vs 不含税收入），合并后数据不一致"

新策略对此的缓解:

1. **同年不混标签**(`dict.setdefault`):任一日历年的值只来自单一 XBRL tag,口径不会在年内被搅混。
2. **优先级显式编码在 `TAG_MAP` 顺序中**:含税/不含税、lease-inclusive/legacy 之类的口径偏好由人工排序决定,而非数据驱动。
3. **跨年口径切换的风险仍存在**:例如某公司 2015–2020 用 `LongTermDebt`、2021+ 用 lease-inclusive 标签,合并后的时间序列在 2020/2021 之间会有口径阶跃。这是已知遗留风险,代价是换取"有数据胜过无数据"(完整 10 年序列 > 只有 1 年新数据)。
4. **TAG_MAP 排序需小心**:新增候选标签时必须明确口径关系(参见 `long_term_debt` 中的内联注释),否则可能引入不易察觉的跨年偏差。

## 后果

**正面**:
- 保留方案 C 的"自动适应不同公司 XBRL 习惯"优势
- 修复 PR #15 中 KO ASC 842 类型的历史塌缩
- 每年的值口径单一(同年不混标签)

**负面**:
- 跨年口径切换的潜在偏差(见上文第 3 点)
- `TAG_MAP` 排序成为隐式契约:reviewer 修改顺序时需理解口径关系

**缓解措施**:
- `TAG_MAP` 候选链就近加入注释说明口径偏好(已对 `long_term_debt` 实施)
- 新增 5 条专项单测(`tests/services/test_sec_agent.py`)覆盖 merge-by-year、同年早 tag 胜出、纯 legacy 无回归、无匹配、季度过滤
- 后续如果跨年口径阶跃成为实际问题,再考虑显式的 unit-of-measure 标注或单独 ADR 处理
