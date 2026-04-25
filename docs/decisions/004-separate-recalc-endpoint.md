# ADR 004: Separate Recalculation Endpoint

**状态**: 已采纳
**日期**: 2025-04 (项目初始设计)
**影响节点**: dynamic_dcf (交互式重算)
**相关代码**: `backend/api/routes.py` → `POST /api/recalculate-dcf`, `backend/api/dependencies.py`

## 背景

用户在前端通过滑块调整 DCF 假设参数（增长率、WACC、永续增长率）后，需要看到新的估值结果。

## 考虑的方案

### 方案 A: 重新触发整个 SSE 分析流
- 调用 `GET /api/analyze/{ticker}` 重新走完 8 个节点
- 问题：需要重新调用 SEC API（有速率限制，10 req/s）
- 问题：需要重新跑所有节点（新闻获取、LLM 调用），等待时间长
- 问题：用户只想调整 DCF 参数，其他结果不应改变

### 方案 B: 前端纯本地重算 ✓ 不可行
- 前端拿到 FCF 数据后直接算 DCF
- 问题：`compute_dcf()` 包含复杂逻辑（WACC 估算、两阶段模型），前后端实现要同步维护
- 问题：将业务逻辑泄漏到前端

### 方案 C: 独立的 POST 重算端点 + 内存缓存 ✓
- `POST /api/recalculate-dcf` 接受新参数
- 从内存缓存读取 `CompanyFinancials`（30 分钟 TTL）
- 只调用 `compute_dcf()` 重算，毫秒级返回
- 前端局部更新 4 个组件

## 决策

采用方案 C。

**缓存策略**: `_financials_cache` 在 SSE 流完成后缓存 `CompanyFinancials` 对象，TTL 30 分钟。缓存键为 ticker 字符串。

## 后果

**正面**:
- 响应毫秒级（只算 DCF，不调外部 API）
- 不触发 SEC 速率限制
- 前端无需重连 SSE
- 业务逻辑留在后端（单一 `compute_dcf()` 实现）

**负面**:
- 缓存过期后（30 分钟）需要重新分析
- 如果 event_impact 已修改了 DCF 参数，用户在重算端点无法看到事件修正的影响（重算基于原始 financials）

**缓解**: 缓存过期返回 HTTP 404，前端提示用户重新分析。前端 `strategy_dashboard` 在 DCF 滑块交互时直接在本地重算安全边际/信号（阈值逻辑与后端一致），不依赖重算端点。
