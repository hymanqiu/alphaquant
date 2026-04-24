# ADR 005: FMP /stable/ API as Market Data Source

**状态**: 已采纳
**日期**: 2025-04 (项目初始设计)
**影响节点**: relative_valuation, strategy
**相关代码**: `backend/services/market_data.py`

## 背景

DCF 计算的内在价值需要与实时市场价格对比，才能给出买入建议。项目原本只有 SEC EDGAR 基本面数据，没有股价来源。

## 考虑的方案

### 方案 A: yfinance
- Python 库，社区广泛使用
- 问题：依赖 pandas + numpy（重型依赖，项目是纯 httpx + pydantic 架构）
- 问题：同步库，与项目全 async (FastAPI + httpx) 架构冲突
- 问题：无官方 API 支持，Yahoo 可能随时封禁

### 方案 B: Yahoo Finance 直连
- 无需额外库，直接 HTTP 请求
- 问题：无官方 API，端点频繁变更
- 问题：需要处理反爬虫机制（cookie、crumb）
- 问题：不稳定，不适合生产环境

### 方案 C: FMP (Financial Modeling Prep) /stable/ API ✓
- 官方 API，有 SLA
- 通过现有 `httpx` 调用，零新增依赖
- FMP 于 2025 年 8 月废弃 `/api/v3/` 和 `/api/v4/`，迁移到 `/stable/` 端点
- Free plan 可用（有速率限制）
- 提供：实时报价、历史行情、同业公司、TTM 估值乘数

### 方案 D: Finnhub (仅限新闻/情绪)
- 已用于新闻和内部人情绪
- 不提供股价/历史行情/同业数据（Free plan）

## 决策

采用方案 C。通过 `MarketDataClient`（httpx）封装所有 FMP 调用。

**端点映射**:
| 功能 | 端点 |
|------|------|
| 实时报价 | `GET /stable/quote?symbol=` |
| 历史行情 | `GET /stable/historical-price-eod/full?symbol=` |
| 同业公司 | `GET /stable/stock-peers?symbol=` |
| TTM 指标 | `GET /stable/ratios-ttm?symbol=` |

## 后果

**正面**:
- 零新增依赖，与现有技术栈一致
- API 稳定，有官方支持
- 优雅降级：`AQ_FMP_API_KEY` 未设置时，relative_valuation 和 strategy 节点自动跳过，不阻塞主流程

**负面**:
- 需要 API Key（Free plan 可用但有速率限制）
- Free plan 的数据覆盖范围有限（某些小盘股可能无同业数据）
- 第三方服务依赖（FMP 宕机则无市场数据）

**降级设计**:
```
AQ_FMP_API_KEY="" → get_current_price() 返回 None
    → relative_valuation: price_available=false
    → strategy: 跳过
    → 用户仍可看到 DCF 估值，只是没有买入策略
```

**未决问题**:
- [ ] 是否需要 fallback 数据源（如 Alpha Vantage）应对 FMP 宕机
- [ ] 是否应该缓存历史行情数据（减少重复 API 调用）
