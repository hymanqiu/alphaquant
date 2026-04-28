# ADR 007: Three-Layer Cost Guardrails

**状态**: 已采纳
**日期**: 2026-04-24 (v0.5.0, Phase 1)
**影响节点**: 所有 LLM 节点 + `/api/analyze` / `/api/recalculate-dcf` 路由
**相关代码**: `backend/services/rate_limit.py`, `backend/services/llm/budget.py`, `backend/services/runtime_settings.py`, `backend/api/admin.py`

## 背景

公开链接前必须解决的两类风险：

1. **DDoS / 滥用**：单个 IP 一分钟刷 100 次 `/analyze`，每次触发 8-12 个外部 API 调用（SEC + FMP + Finnhub + LLM × N），账户被刷爆。
2. **LLM 成本失控**：DeepSeek 单次 ~$0.01，但出错的 prompt 或者 oversized input 可能跑出 $1+ 单次调用；每天累计可能超出预算。

需要在**调用真正发生之前**就拦下来，并且支持运维**不重启就能调阈值**。

## 考虑的方案

### 方案 A: 仅靠 LLM provider 的 rate limit
- 不做事，依赖 DeepSeek 自己限流
- 问题：provider 限流通常是按账户的，不区分用户/IP；一个滥用者可以让所有用户的请求都 429
- 问题：账单已经产生才发现来不及

### 方案 B: 应用层单层限流（IP rate limit only）
- 用 `slowapi` 之类做 IP 限流
- 问题：限流不等于成本控制，限流额度内仍可能跑出高成本调用
- 问题：单层不够，被绕过没有第二道防线

### 方案 C: 三层防御（IP 限流 + per-IP 预算 + 全局预算） ✓
- 三层独立触发，互为冗余
- IP 限流挡 DDoS（拒绝路由进入，零调用成本）
- per-IP 预算挡"在限流额度内但调用很贵"
- 全局预算挡"分布式滥用从不同 IP 来的"
- 三层阈值均运行时可调（RuntimeSettings）

## 决策

采用方案 C。

### 三层闸门（从外到内）

```
请求来                         IP=1.2.3.4
  │
  ▼  ① IP 限流 (services/rate_limit.py)
  │   IPRateLimiter.check_and_record(bucket="analyze", client_ip)
  │   24h 滑动窗 dict[(bucket, ip)] -> deque[timestamps]
  │   超限 → HTTP 429 + Retry-After (零调用成本)
  ▼
  bind_client_ip(ip) 进 contextvars
  ▼
  Pro 节点跑到 LLMClient.complete_json
  ▼  ② Per-IP LLM 预算 (services/llm/budget.py)
  │   accounting.spend_since(24h, client_ip="1.2.3.4") ≥ AQ_LLM_PER_IP_DAILY_BUDGET_USD?
  │   超限 → LLMBudgetExceeded(scope=per_ip) → 节点 except LLMError → 降级
  ▼
  ▼  ③ 全局预算
  │   accounting.spend_since(24h, all) ≥ AQ_LLM_DAILY_BUDGET_USD?
  │   超限 → LLMBudgetExceeded(scope=global) → 当天剩余所有 LLM 调用降级
  ▼
  实际 HTTPS → DeepSeek
  ▼
  accounting.record(client_ip, input/output_tokens, cost) → 进 24h 滑动窗
```

### Runtime 配置（两层）

env 提供启动默认，admin API 提供运行时覆盖。读取统一走 `RuntimeSettings.snapshot()` —— admin 改完下次调用立即生效。

```python
# services/runtime_settings.py 暴露的字段
llm_daily_budget_usd: float           # 全局, 默认 5.0
llm_per_ip_daily_budget_usd: float    # 单 IP, 默认 0.25
rate_limit_analyze_per_ip_day: int    # /analyze, 默认 3
rate_limit_recalculate_per_ip_day: int # /recalculate-dcf, 默认 30
```

### Admin API（`/api/admin/`，Bearer token）

```bash
GET  /api/admin/usage              # 24h 花费 + 按 task / IP 分组
PATCH /api/admin/settings          # 改任一阈值，立即生效
POST /api/admin/settings/reset     # 一键回 env 默认
```

### 存储

- 限流：内存 `defaultdict[(bucket, ip), deque[timestamps]]`，FIFO 清理 24h 之外
- 预算：内存 ring buffer (max 2000 条 `LLMUsageRecord`) + 每条 JSON 日志一行（log pipeline 可聚合）

## 后果

**正面**:
- 公开链接放心发——最坏情况花费被双层预算扣死
- 任意 IP 一天花费上限 $0.25 = 即使限流被绕过单 IP 损失可控
- 所有阈值热改：发推前临时压低 budget；发推后看到反响调高
- 三层独立 → 任一层有 bug 不会让另两层也失效
- 单 admin API 同时管"安全"和"成本"，运维心智一致

**负面**:
- 单实例内存存储，多实例部署需要换 Redis（current scope 是 single instance MVP）
- 进程重启 → 内存数据清空 → 当天累计花费"重置" → 短窗口内的预算保护被绕过（缓解：日志可重建；正式环境会接 Postgres）
- IP 限流对走代理 / NAT 的真实用户不友好（缓解：未来加入登录用户后用 user_id 替代 IP 作为 key）
- 每个 LLM 调用前多两次 dict 查询 + 一次 sum（开销 microseconds 级，可忽略）

**降级行为**:

| 触发 | 用户体验 |
|------|---------|
| HTTP 429 | 前端应该显示 "今日免费额度用完, 24h 后重置 / 升级 Pro"（待做：见 [DEVELOPMENT.md 已知 tech debt](../../DEVELOPMENT.md)） |
| LLMBudgetExceeded | 用户看不到差别（和 LLM provider 自身错误走同一降级路径，节点 skip） |
| 节点 skip | 上层分析继续；只是缺这部分 LLM 输出 |

**未决问题**:
- [ ] 是否要给 Pro 用户更高的限流额度（e.g. 50/day）—— 等 Phase 2 接 auth 后再做（已完成 Phase 2，可以做这个 follow-up）
- [ ] 全局预算耗尽时是否给登录用户透支额度 —— BYOK（[ADR 006](006-unified-llm-client.md) 未来扩展点）解决方案
- [ ] Redis 集群版限流（multi-instance 部署前必需）
