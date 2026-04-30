# ADR 006: Unified LLM Client as Single Chokepoint

**状态**: 已采纳
**日期**: 2026-04-24 (v0.5.0, Phase 1)
**影响节点**: event_sentiment, event_impact, qualitative_analysis, risk_yoy_diff, moat_analysis, investment_thesis
**相关代码**: `backend/services/llm/`, `backend/prompts/`

## 背景

v0.4 之前，每个用 LLM 的节点（`llm_sentiment.py`、`event_impact.py`）自己 `import httpx` 直连 DeepSeek，prompt 写在 Python 字符串常量里，没有统一的 token 计费、错误处理、重试、Provider 抽象。继续这样写下去：

- 加一个 LLM 节点 = 复制 80 行模板代码
- 想换 provider（DeepSeek → OpenAI）= 改 N 个文件
- 想要 budget gate / 限流 = 没法塞进散落的调用点
- prompt 散在代码里，不能 diff 看版本变化

## 考虑的方案

### 方案 A: 继续现状（每个节点自己 httpx）
- 短期最快
- 问题：上面 4 个痛点全部不解决
- 问题：到 Phase 3 多加 5 个 LLM 节点时会爆炸

### 方案 B: 用 LangChain 的 LLM 抽象 (`ChatOpenAI` / `ChatAnthropic` 等)
- 自带 Provider 切换
- 问题：LangChain 的依赖很重，项目刻意保持轻（纯 httpx + pydantic）
- 问题：LangChain 的 prompt 模板系统 (`PromptTemplate`) 和 Pydantic 校验集成不顺
- 问题：cost / token 追踪不是开箱即用，仍要手写

### 方案 C: 自建 LLMClient 单一入口 ✓
- 100% 走 httpx，零新依赖
- 编排所有横切关注点：prompt 加载、输入净化、预算检查、重试、计费、Pydantic 校验
- 通过 `task_tag` 字符串区分调用类型 → admin 可以基于 task_tag 做路由 / 预算分桶

## 决策

采用方案 C。`backend/services/llm/` 提供唯一调用入口：

```python
LLMClient.complete_json(
    prompt_name="moat_analysis",        # 从 backend/prompts/{name}_v{version}.yaml 加载
    version=1,
    variables={"ticker": ..., ...},
    response_model=MoatInsight,         # Pydantic 强制结构
    task_tag="moat",                    # budget / 路由 / 计费 / 日志的归类键
)
```

**搜不到任何节点直接 `httpx.post` 到 LLM provider 的代码**——这是项目的不变性约束。

### 模块拆分

| 文件 | 职责 |
|------|------|
| `client.py` | `LLMClient` 主类 + 全局 singleton + `complete_json` 编排所有步骤 |
| `providers.py` | `OpenAICompatibleProvider`（DeepSeek / OpenAI / 任何 OpenAI 协议兼容） |
| `sanitize.py` | HTML 转义 + 控制字符剔除 + `<<<USER_CONTENT>>>` 边界包裹 + 注入模式检测 |
| `accounting.py` | `AccountingStore`：每次调用结构化日志一行 + 24h 滑动窗成本聚合（per-IP & 全局） |
| `budget.py` | `BudgetGate`：双闸熔断（详见 [ADR 007](007-three-layer-cost-guardrails.md)） |
| `errors.py` | `LLMError` 基类 + `LLMConfigError` / `LLMProviderError` / `LLMParseError` / `LLMBudgetExceeded` |

### Prompt 库

`backend/prompts/<name>_v<N>.yaml`，每个文件含 `system` / `user` 两段 + tuning 默认（`temperature` / `max_tokens`） + `response_schema` 名称。`load_prompt(name, version)` 启动期解析 + 缓存，运行期 0 额外 IO。

### Provider 路由

`task_tag in {"thesis", "report_summary"}` 路由到 narrative provider（`AQ_LLM_NARRATIVE_*`）；其它走 primary。narrative 没配则 fallback 到 primary。

### IP propagation

每次请求 `bind_client_ip(ip)` 进 `contextvars.ContextVar`；`LLMClient.complete_json` 内部 `current_client_ip()` 读取，写入 `accounting.record(client_ip=...)` —— 不用层层传参。

## 后果

**正面**:
- 加一个 LLM 节点 = 加一个 prompt YAML + 一个 Pydantic 模型 + 一个节点（节点本身只 ~100 行）
- 切换 provider 改一个 env var；切换 task → narrative provider 路由改一个常量
- Budget gate / 计费 / 日志全部一次实现，所有调用点免费享受
- Prompt 可以 git diff，可以版本化（`v1` / `v2` 共存）
- 测试容易：mock `LLMClient.complete_json`，节点其它逻辑保持纯函数

**负面**:
- 多了一层抽象，新人需要先理解 `LLMClient` 才能加节点（缓解：本 ADR + node 模板）
- Pydantic 校验失败的错误信息有时不够友好（缓解：`LLMParseError` 包了 ValidationError 的 message）
- httpx 客户端是全局 singleton，并发限制由其内部连接池控制（够用但不够灵活）

**未来扩展点**:
- [ ] 多 Provider 路由表（admin 在 RuntimeSettings 里热改）—— L2 settings 工作
- [ ] 用户级 BYOK（per-user API key）—— L4 settings 工作
- [ ] Streaming 支持 (`complete_text` 当前不实现 streaming) —— Q&A chat 功能时需要
