# ADR 002: Why Two-Stage DCF (Not Three-Stage)

**状态**: 已采纳
**日期**: 2025-04 (项目初始设计)
**影响节点**: dynamic_dcf, event_impact
**相关代码**: `backend/agents/nodes/dcf_model.py` → `compute_dcf()`

## 背景

DCF 估值模型有多种阶段划分方式。核心问题是如何建模公司从高增长期过渡到成熟期的过程。

## 考虑的方案

### 方案 A: 单阶段 (永续增长)
- 假设公司立刻以恒定增长率永远增长
- 适用于成熟、稳定增长的公司（如公用事业）
- 问题：对高增长公司（如 NVDA）严重低估增长潜力

### 方案 B: 两阶段 ✓
- Phase 1 (5年): 恒定高增长率
- Phase 2 (5年): 线性衰减到永续增长率
- 平衡了简洁性和准确性

### 方案 C: 三阶段
- Phase 1: 超高增长
- Phase 2: 过渡期
- Phase 3: 稳定增长
- 理论上更精确
- 问题：需要更多参数（两段增长率、两段衰减），而 SEC 数据往往不足以支撑这么多假设

## 决策

采用方案 B（两阶段）。10 年预测期，Phase 1 恒定高增长 5 年，Phase 2 线性衰减 5 年。

## 后果

**正面**:
- 只需 3 个核心假设：增长率、WACC、永续增长率
- 线性衰减比恒定增长更合理，又不至于参数爆炸
- 用户可通过前端滑块直接调参，模型可解释性强

**负面**:
- 恒定高增长 5 年对某些公司可能过长（如已进入稳定期的公司）
- 线性衰减不是唯一的衰减方式（指数衰减、H-model 也是合理选择）

**假设值来源**:
| 参数 | 值 | 来源 |
|------|-----|------|
| risk_free_rate | 4.5% | 硬编码 (美国10年期国债近似) |
| equity_risk_premium | 5.5% | 硬编码 (历史平均) |
| beta | 动态 / 1.2 | FMP `/stable/profile` 实时获取，缺失时回退 1.2 |
| tax_rate | 21% | 硬编码 (美国联邦企业税) |
| growth_cap | 30% | 防止不合理的极高增长 |
| terminal_growth | 3.0% | 固定假设 (近似GDP增长) |
| WACC floor | 4% | 防止不合理低价折现（原 6%，对低 beta 防御股偏高） |

**净债务调整**: 自 2026-05 起，`per_share = (EV + cash − total_debt) / shares`，而非早期版本的 `EV / shares`。后者忽略资本结构，对 KO 这类高净债公司高估、对 GOOG 这类高净现金公司低估。`total_debt` 由 `sec_agent._compute_total_debt` 按日历年聚合：long-term debt（含 ASC 842 finance lease）+ short-term borrowings / commercial paper + current portion of long-term debt。

**经营租赁负债 (operating lease liabilities) 不计入 total_debt** —— 这是个有意识的取舍：
- **支持纳入**：ASC 842 后租赁负债出现在资产负债表，评级机构 (S&P / Moody's) 视同负债处理。
- **支持排除（本项目立场）**：经营租赁通常不带显式利息（经济实质是租金 ≈ 经营性支出），纳入会让 cost-of-debt 分母虚增、低估 WACC，且与 `interest_expense` 实际不匹配。许多教科书 DCF / 价值投资框架同样不计。
- **可重新评估的信号**：若发现某行业（航空、零售）DCF 系统性偏离 textbook，可在 `_compute_total_debt` 加 `OperatingLeaseLiability` component 并同步 `interest_expense` 处理重估租赁利息部分。

**负权益兜底**: 若 `stockholders_equity ≤ 0`（重度回购公司如 MCD），且 `market_profile.market_cap` 可用，则用市值替代权益权重计算 WACC，避免 E/V 为负数导致的数学异常。

**未决问题**:
- [x] beta 已通过 FMP 动态获取（risk_free_rate 仍硬编码）
- [ ] 是否应支持用户选择衰减方式（线性 vs H-model）
- [ ] 30% 增长率上限对 NVDA 类超高增长公司低估明显，需考虑动态上限
