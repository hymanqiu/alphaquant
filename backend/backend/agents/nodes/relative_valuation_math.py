"""Pure computation helpers for relative valuation (no I/O)."""

from __future__ import annotations

import statistics
from typing import Any

from backend.models.financial import AnnualMetric


def safe_divide(a: float, b: float) -> float | None:
    return a / b if b != 0 else None


def latest(metrics: list[AnnualMetric]) -> float | None:
    return metrics[-1].value if metrics else None


def by_year(metrics: list[AnnualMetric]) -> dict[int, float]:
    return {m.calendar_year: m.value for m in metrics}


def median(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.median(values)


def percentile_rank(value: float, population: list[float]) -> float | None:
    """Return the percentile of *value* within *population* (0–100)."""
    if not population:
        return None
    rank = sum(1 for v in population if v <= value)
    return round(rank / len(population) * 100, 1)


def compute_earnings_cagr(eps: list[AnnualMetric], years: int = 3) -> float | None:
    """CAGR of diluted EPS over the last *years* periods."""
    if len(eps) < years + 1:
        return None
    start = eps[-(years + 1)].value
    end = eps[-1].value
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def compute_ffo(
    net_income: float | None, d_and_a: float | None
) -> float | None:
    """Simplified FFO = Net Income + D&A. Excludes property-sale gains."""
    if net_income is None or d_and_a is None:
        return None
    return net_income + d_and_a


def compute_dividend_yield(
    last_dividend: float | None, current_price: float | None
) -> float | None:
    """Dividend yield as a percentage (e.g. 3.25 for 3.25%)."""
    if not last_dividend or not current_price or current_price <= 0:
        return None
    return round(last_dividend / current_price * 100, 2)


def compute_current_multiples(
    financials: Any,
    current_price: float,
    last_dividend: float | None = None,
) -> dict[str, Any]:
    """Compute current market multiples from financials + live price."""
    shares = latest(financials.diluted_shares)
    if not shares or shares <= 0:
        return {"price_available": True, "multiples": {}}

    market_cap = current_price * shares
    lt_debt = latest(financials.long_term_debt) or 0
    cash = latest(financials.cash_and_equivalents) or 0
    ev = market_cap + lt_debt - cash

    revenue = latest(financials.revenue)
    net_income = latest(financials.net_income)
    op_income = latest(financials.operating_income)
    fcf = latest(financials.free_cash_flow)
    equity = latest(financials.stockholders_equity)
    eps = latest(financials.diluted_eps)
    d_and_a = latest(getattr(financials, "depreciation_and_amortization", []) or [])

    multiples: dict[str, float | None] = {}
    multiples["pe"] = safe_divide(current_price, eps) if eps and eps > 0 else None
    multiples["pb"] = safe_divide(market_cap, equity) if equity and equity > 0 else None
    multiples["ps"] = safe_divide(market_cap, revenue) if revenue and revenue > 0 else None
    multiples["ev_to_revenue"] = safe_divide(ev, revenue) if revenue and revenue > 0 else None
    multiples["ev_to_ebit"] = safe_divide(ev, op_income) if op_income and op_income > 0 else None
    multiples["ev_to_fcf"] = safe_divide(ev, fcf) if fcf and fcf > 0 else None

    ffo = compute_ffo(net_income, d_and_a)
    multiples["p_ffo"] = safe_divide(market_cap, ffo) if ffo and ffo > 0 else None

    multiples["dividend_yield"] = compute_dividend_yield(last_dividend, current_price)

    pe = multiples["pe"]
    earnings_growth = compute_earnings_cagr(financials.diluted_eps, years=3)
    if pe and earnings_growth and earnings_growth > 0:
        multiples["peg"] = round(pe / (earnings_growth * 100), 2)
    else:
        multiples["peg"] = None

    return {
        "price_available": True,
        "market_cap": round(market_cap, 2),
        "enterprise_value": round(ev, 2),
        "multiples": {k: round(v, 2) if v is not None else None for k, v in multiples.items()},
    }


def compute_historical_multiples(
    financials: Any,
    annual_prices: dict[int, float],
) -> dict[str, Any]:
    """Compute historical multiples for each year with both price + SEC data."""
    shares_by_year = by_year(financials.diluted_shares)
    revenue_by_year = by_year(financials.revenue)
    ni_by_year = by_year(financials.net_income)
    op_income_by_year = by_year(financials.operating_income)
    equity_by_year = by_year(financials.stockholders_equity)
    debt_by_year = by_year(financials.long_term_debt)
    cash_by_year = by_year(financials.cash_and_equivalents)
    da_by_year = by_year(
        getattr(financials, "depreciation_and_amortization", []) or []
    )

    series: dict[str, list[dict[str, Any]]] = {
        "pe": [], "pb": [], "ps": [],
        "ev_to_revenue": [], "ev_to_ebit": [], "p_ffo": [],
    }

    common_years = sorted(
        set(annual_prices.keys()) & set(shares_by_year.keys())
    )

    for year in common_years:
        price = annual_prices[year]
        shares = shares_by_year[year]
        if shares <= 0:
            continue
        mkt_cap = price * shares
        ev = mkt_cap + (debt_by_year.get(year, 0) or 0) - (cash_by_year.get(year, 0) or 0)

        rev = revenue_by_year.get(year)
        ni = ni_by_year.get(year)
        oi = op_income_by_year.get(year)
        eq = equity_by_year.get(year)
        da = da_by_year.get(year)

        if ni and ni > 0:
            series["pe"].append({"year": year, "value": round(price / (ni / shares), 2)})
        if eq and eq > 0:
            series["pb"].append({"year": year, "value": round(mkt_cap / eq, 2)})
        if rev and rev > 0:
            series["ps"].append({"year": year, "value": round(mkt_cap / rev, 2)})
            series["ev_to_revenue"].append({"year": year, "value": round(ev / rev, 2)})
        if oi and oi > 0:
            series["ev_to_ebit"].append({"year": year, "value": round(ev / oi, 2)})
        ffo = compute_ffo(ni, da)
        if ffo and ffo > 0:
            series["p_ffo"].append({"year": year, "value": round(mkt_cap / ffo, 2)})

    stats: dict[str, Any] = {}
    for name, entries in series.items():
        values = [e["value"] for e in entries]
        med = median(values)
        avg = round(sum(values) / len(values), 2) if values else None
        stats[name] = {
            "series": entries,
            "median": round(med, 2) if med is not None else None,
            "average": avg,
            "count": len(values),
        }

    return stats
