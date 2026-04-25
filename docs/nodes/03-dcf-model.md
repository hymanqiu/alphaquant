# Node 3: dynamic_dcf

> 图位置: `financial_health_scan → dynamic_dcf → relative_valuation`

## 职责

基于历史 FCF 数据，使用两阶段 DCF 模型估算公司内在价值。支持前端滑块实时重算。

## 输入

> **真相源**: `backend/models/agent_state.py` — `AnalysisState`

### State 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `financials` | `CompanyFinancials` | ✅ | → [Node 1 输出](01-fetch-sec-data.md#companyfinancials-结构体) |

### 子字段访问

节点实际从 `financials` 访问以下子字段 (`_run_dcf`, line 146):

| 访问路径 | 类型 | 必需 | 用途 |
|----------|------|:----:|------|
| `financials.entity_name` | `str` | ✅ | UI 显示 |
| `financials.ticker` | `str` | ✅ | 日志 |
| `financials.free_cash_flow` | `list[AnnualMetric]` | ✅ | FCF 时间序列，需 ≥ 1 年；CAGR 需 ≥ 3 年 |
| `financials.long_term_debt[-1].value` | `float \| None` | ⬜ | WACC 债务部分 (缺失 → 全权益模型) |
| `financials.stockholders_equity[-1].value` | `float \| None` | ⬜ | WACC 权益部分 |
| `financials.interest_expense[-1].value` | `float \| None` | ⬜ | 计算债务成本 |
| `financials.diluted_shares[-1].value` | `float \| None` | ⬜ | 每股价值 (缺失 → `intrinsic_value_per_share = None`) |

### NVDA 示例 (输入子字段)

```json
{
  "entity_name": "NVIDIA Corp",
  "ticker": "NVDA",
  "free_cash_flow": [
    {"calendar_year": 2021, "value": 4112000000},
    {"calendar_year": 2022, "value": 3821000000},
    {"calendar_year": 2023, "value": 6908000000},
    {"calendar_year": 2024, "value": 26657000000}
  ],
  "long_term_debt":    [{"calendar_year": 2024, "value": 8461000000}],
  "stockholders_equity": [{"calendar_year": 2024, "value": 43585000000}],
  "interest_expense":  [{"calendar_year": 2024, "value": 247000000}],
  "diluted_shares":    [{"calendar_year": 2024, "value": 2487000000}]
}
```

---

## 输出

### State 更新

| 字段 | 类型 | 说明 |
|------|------|------|
| `dcf_result` | `dict \| None` | DCF 计算结果 (结构见下) |
| `reasoning_steps` | `list[str]` | 追加到推理链 |

### `dcf_result` 结构体

> **源码**: `backend/agents/nodes/dcf_model.py` `compute_dcf()` line 100-121

```python
{
    "projected_fcf": [                        # list[dict] — 10 年预测 FCF
        {
            "year": int,                      # 1..10
            "fcf": float,                     # 预测 FCF ($)
            "growth_rate": float,             # 当年增长率 (%)
            "discount_factor": float,         # 折现因子
            "present_value": float,           # 现值 ($)
        },
        ...
    ],
    "terminal_value": float,                  # 终值 ($)
    "terminal_pv": float,                     # 终值现值 ($)
    "pv_fcf_sum": float,                      # FCF 现值之和 ($)
    "enterprise_value": float,                # 企业价值 = pv_fcf_sum + terminal_pv ($)
    "intrinsic_value_per_share": float | None, # 内在价值 ($/股), shares 缺失时为 None
    "assumptions": {
        "growth_rate": float,                 # 初始增长率 (%)
        "terminal_growth_rate": float,        # 永续增长率 (%), 固定 3.0
        "discount_rate": float,               # WACC (%)
        "projection_years": int,              # 预测年数, 固定 10
        "latest_fcf": float,                  # 最新 FCF ($)
    },
}
```

> **增长率估算**: `3yr CAGR × 0.6 + 5yr CAGR × 0.4`，上限 30%，下限 2%。不足时回退 10%。
> **WACC**: `risk_free(4.5%) + beta(1.2) × ERP(5.5%)` 基础 + 债务调整 (无债务数据时回退 cost_of_equity)，下限 6%。

### NVDA 示例 (输出)

```json
{
  "dcf_result": {
    "projected_fcf": [
      {"year": 1, "fcf": 31047000000, "growth_rate": 16.47, "discount_factor": 0.911826, "present_value": 28310000000},
      {"year": 2, "fcf": 36161000000, "growth_rate": 16.47, "discount_factor": 0.831427, "present_value": 30065000000},
      {"year": 5, "fcf": 57132000000, "growth_rate": 16.47, "discount_factor": 0.630320, "present_value": 36012000000},
      {"year": 6, "fcf": 65003000000, "growth_rate": 13.78, "discount_factor": 0.574742, "present_value": 37360000000},
      {"year": 10, "fcf": 85201000000, "growth_rate": 3.0, "discount_factor": 0.397303, "present_value": 33851000000}
    ],
    "terminal_value": 1315700000000,
    "terminal_pv": 522730000000,
    "pv_fcf_sum": 342720000000,
    "enterprise_value": 865450000000,
    "intrinsic_value_per_share": 347.99,
    "assumptions": {
      "growth_rate": 16.47,
      "terminal_growth_rate": 3.0,
      "discount_rate": 9.67,
      "projection_years": 10,
      "latest_fcf": 26657000000
    }
  },
  "reasoning_steps": [
    "Latest FCF: $26,657,000,000",
    "Estimated growth rate: 16.5% (capped at 30%)",
    "WACC (discount rate): 9.67%",
    "Intrinsic value per share: $347.99"
  ]
}
```

## 核心算法

```
1. 估算增长率:
   ├── _fcf_cagr(fcf, 3) → 3年 CAGR
   ├── _fcf_cagr(fcf, 5) → 5年 CAGR (数据不足时为 None)
   └── 封顶: min(max(raw_growth, 2%), 30%)

2. 估算 WACC:
   ├── cost_of_equity = risk_free(4.5%) + beta(1.2) × ERP(5.5%) = 11.1%
   ├── cost_of_debt = interest / debt (仅当债务数据完整时)
   ├── WACC = (E/V)×Re + (D/V)×Rd×(1-T)
   └── floor: max(WACC, 6%)
   └── 债务数据缺失 → 回退全权益模型

3. 两阶段 DCF (compute_dcf):
   ├── Phase 1 (Y1-5): 恒定高增长
   ├── Phase 2 (Y6-10): 线性衰减 growth → terminal(3%)
   ├── Terminal Value = Y10_FCF × (1+terminal) / (discount - terminal)
   ├── EV = Σ PV(FCF) + PV(TV)
   └── Intrinsic/Share = EV / diluted_shares
```

## 关键假设

- **两阶段 DCF 而非三阶段** → [ADR 002](../decisions/002-two-stage-dcf.md)
- **独立重算端点而非重跑全图** → [ADR 004](../decisions/004-separate-recalc-endpoint.md)
- WACC 参数硬编码：risk_free=4.5%, ERP=5.5%, beta=1.2, tax=21%
- 增长率上限 30%，WACC 下限 6%，永续增长率固定 3%

## LLM 使用

无。纯计算节点。

## 失败模式与降级

| 场景 | 处理 |
|------|------|
| financials 为 None | ErrorEvent, return None |
| FCF 数据为空 | return None，跳过 DCF |
| 利息/负债缺失 | WACC 回退到全权益模型 (cost_of_equity) |
| diluted_shares 缺失 | `intrinsic_value_per_share = None` |
| 通用异常 | try/except → ErrorEvent |

## 交互式重算

`POST /api/recalculate-dcf` — 从内存缓存 (30min TTL) 读 `CompanyFinancials`，调用 `compute_dcf()` 重算。前端局部更新 dcf_result_card, valuation_gauge, fcf_chart。strategy_dashboard 前端直接重算安全边际。

## 源文件

| 文件 | 职责 |
|------|------|
| `backend/agents/nodes/dcf_model.py` | DCF 节点 + `compute_dcf()` 核心函数 |
| `backend/api/routes.py` | `POST /api/recalculate-dcf` |
| `backend/api/dependencies.py` | 内存缓存 |

## 前端组件

| component_type | 组件 |
|----------------|------|
| `fcf_chart` | `FCFChart` — 历史+预测 FCF 柱状图 |
| `dcf_result_card` | `DCFResultCard` — 内在价值、EV、TV |
| `valuation_gauge` | `ValuationGauge` — 估值仪表 |
| `assumption_slider` | `AssumptionSlider` — 3 参数滑块 + 重算按钮 |

## 未决问题 / TODO

- [ ] risk_free_rate, beta 应从外部 API 动态获取
- [ ] 是否支持用户选择衰减方式（线性 vs H-model）
