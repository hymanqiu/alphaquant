# ADR 003: StreamWriter over astream_events

**状态**: 已采纳
**日期**: 2025-04 (项目初始设计)
**影响节点**: 所有节点
**相关代码**: `backend/agents/value_analyst.py` → `graph.astream(..., stream_mode=["custom", "values"])`

## 背景

LangGraph 提供两种实时流式输出机制。需要选择一种来实现"白盒化"——将分析过程实时展示给用户。

## 考虑的方案

### 方案 A: `astream_events()`
- LangGraph 的标准事件流 API
- 自动捕获所有节点进入/退出、LLM 调用、工具使用等事件
- 问题：产生大量内部回调事件（每个 LLM token 都触发），难以过滤出对用户有意义的事件
- 问题：事件结构复杂，需要大量解析逻辑才能映射到 UI 组件

### 方案 B: `StreamWriter` (writer 参数) ✓
- 每个节点函数接收一个 `writer` 回调参数
- 节点内部显式调用 `writer(event)` 发射自定义事件
- 完全控制：节点决定何时、发什么事件
- 直接映射到 Generative UI 协议的 5 种事件类型

## 决策

采用方案 B。在 `graph.astream(initial_state, stream_mode=["custom", "values"])` 中：
- `"custom"` 接收节点通过 StreamWriter 发射的事件
- `"values"` 接收状态更新（用于缓存 financials）

## 后果

**正面**:
- 每个节点精确控制 SSE 事件，前端渲染逻辑简洁
- 事件结构由 `backend/models/events.py` 定义，类型安全
- 新增节点时无需关心全局事件过滤

**负面**:
- 节点必须手动发射每个事件，遗漏会导致前端无显示
- 无法自动获得 LLM 内部推理过程的 token 级流式（但项目选择了"总结性"展示而非逐 token 展示）

**权衡**: 放弃了 token 级实时性，换取了事件结构的简洁性和可控性。对投资分析场景而言，"步骤完成通知"比"逐 token 推理"更有价值。
