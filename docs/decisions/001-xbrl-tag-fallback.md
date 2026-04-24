# ADR 001: XBRL Tag Fallback with Best-Match Selection

**状态**: 已采纳
**日期**: 2025-04 (项目初始设计)
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

### 方案 C: 所有候选都尝试，选择 latest_year 值最大的 ✓
- 优先选择"有最新数据的标签"
- 如果新标签有 2025 数据而旧标签只到 2023，自动选新标签
- 如果旧标签反而更新（如公司回退到旧标签），也能正确选择

## 决策

采用方案 C。在 `_extract_annual_metrics()` 中：
1. 遍历 `TAG_MAP` 中定义的所有候选标签
2. 对每个候选调用 `_extract_for_tag()` 获取年序列
3. 选择 `latest_year` 值最大的那个

## 后果

**正面**:
- 自动适应不同公司的 XBRL 标签使用习惯
- 无需手动为每个公司配置标签偏好

**负面**:
- 如果两个标签都有最新数据但数值不同（口径差异），会选择值较大的那个，可能引入系统性偏差
- `TAG_MAP` 需要人工维护，新增标签需要更新

**缓解措施**: `TAG_MAP` 定义了标签候选链（每个财务概念 1-5 个标签），覆盖了 SEC EDGAR 中最常见的变体。
