"""Map GICS sector / industry to the most appropriate valuation multiples.

The mapping is deterministic and hardcoded. An ``IndustryExplainer`` protocol
is exposed so a future LLM-backed explainer can be injected without changing
callers.
"""

from __future__ import annotations

from typing import Any, Protocol

# GICS sector names as FMP returns them via /stable/profile.
# Note: FMP historically uses "Technology" but GICS officially says
# "Information Technology" — we include both keys to be resilient.
GICS_SECTOR_MULTIPLES: dict[str, dict[str, Any]] = {
    "Financials": {
        "recommended": ["pe", "pb"],
        "explanation": (
            "Banks and insurers are capital-structure businesses; P/B dominates "
            "and P/E is secondary. EV-based multiples distort because deposits "
            "are not debt."
        ),
    },
    "Financial Services": {
        "recommended": ["pe", "pb"],
        "explanation": (
            "Financial services firms are capital-structure businesses; P/B "
            "dominates and P/E is secondary."
        ),
    },
    "Real Estate": {
        "recommended": ["p_ffo", "ev_to_ebit"],
        "explanation": (
            "REITs' GAAP earnings are distorted by depreciation of appreciating "
            "property. P/FFO is the industry standard."
        ),
    },
    "Utilities": {
        "recommended": ["pe", "dividend_yield", "ev_to_ebit"],
        "explanation": (
            "Regulated, stable cash-flow businesses priced as yield proxies — "
            "dividend yield and P/E dominate."
        ),
    },
    "Information Technology": {
        "recommended": ["pe", "ps", "ev_to_revenue"],
        "explanation": (
            "Growth-heavy; P/S and EV/Revenue normalize across varying margin "
            "profiles."
        ),
    },
    "Technology": {
        "recommended": ["pe", "ps", "ev_to_revenue"],
        "explanation": (
            "Growth-heavy; P/S and EV/Revenue normalize across varying margin "
            "profiles."
        ),
    },
    "Energy": {
        "recommended": ["ev_to_ebit", "pb", "ev_to_fcf"],
        "explanation": (
            "Cyclical commodity earnings; EV-based multiples and reserve-backed "
            "P/B smooth the cycle."
        ),
    },
    "Materials": {
        "recommended": ["ev_to_ebit", "pb", "ev_to_revenue"],
        "explanation": (
            "Capex-heavy cyclicals; EV-based multiples account for debt "
            "financing."
        ),
    },
    "Basic Materials": {
        "recommended": ["ev_to_ebit", "pb", "ev_to_revenue"],
        "explanation": (
            "Capex-heavy cyclicals; EV-based multiples account for debt "
            "financing."
        ),
    },
    "Industrials": {
        "recommended": ["pe", "ev_to_ebit", "ev_to_fcf"],
        "explanation": (
            "Mature-growth cash generators; earnings and FCF-based multiples "
            "both apply."
        ),
    },
    "Consumer Discretionary": {
        "recommended": ["pe", "ev_to_ebit", "peg"],
        "explanation": (
            "Growth-sensitive earnings; PEG adjusts P/E for cyclical growth."
        ),
    },
    "Consumer Cyclical": {
        "recommended": ["pe", "ev_to_ebit", "peg"],
        "explanation": (
            "Growth-sensitive earnings; PEG adjusts P/E for cyclical growth."
        ),
    },
    "Consumer Staples": {
        "recommended": ["pe", "ev_to_ebit", "dividend_yield"],
        "explanation": (
            "Stable cash flows; P/E and dividend yield for defensive valuation."
        ),
    },
    "Consumer Defensive": {
        "recommended": ["pe", "ev_to_ebit", "dividend_yield"],
        "explanation": (
            "Stable cash flows; P/E and dividend yield for defensive valuation."
        ),
    },
    "Health Care": {
        "recommended": ["pe", "ev_to_ebit", "ps"],
        "explanation": (
            "Pharma and medical devices on P/E and EV/EBIT; early-stage biotech "
            "defaults to P/S when earnings are negative."
        ),
    },
    "Healthcare": {
        "recommended": ["pe", "ev_to_ebit", "ps"],
        "explanation": (
            "Pharma and medical devices on P/E and EV/EBIT; early-stage biotech "
            "defaults to P/S when earnings are negative."
        ),
    },
    "Communication Services": {
        "recommended": ["pe", "ev_to_ebit", "ev_to_fcf"],
        "explanation": (
            "Blend of telecom (FCF-driven) and media/internet "
            "(earnings-driven) sub-industries."
        ),
    },
}

# Industry-level refinements. These fire when the finer FMP "industry" field
# matches, overriding the sector default.
INDUSTRY_OVERRIDES: dict[str, dict[str, Any]] = {
    "Insurance": {
        "recommended": ["pb", "pe"],
        "explanation": (
            "Insurers are valued on book value (investment float) plus earnings."
        ),
    },
    "Insurance - Diversified": {
        "recommended": ["pb", "pe"],
        "explanation": "Diversified insurers are valued on book value plus earnings.",
    },
    "Insurance - Life": {
        "recommended": ["pb", "pe"],
        "explanation": "Life insurers are valued on book value plus earnings.",
    },
    "Insurance - Property & Casualty": {
        "recommended": ["pb", "pe"],
        "explanation": "P&C insurers are valued on book value plus earnings.",
    },
    "Asset Management": {
        "recommended": ["pe", "ev_to_ebit"],
        "explanation": (
            "Fee-based asset managers earn on AUM; P/E and EV/EBIT apply, "
            "not P/B."
        ),
    },
}

_DEFAULT_RECOMMENDATION: dict[str, Any] = {
    "recommended": ["pe", "pb", "ps", "ev_to_revenue", "ev_to_ebit", "ev_to_fcf"],
    "explanation": "Sector unclassified; showing the standard multiple set.",
}


def recommended_multiples(
    sector: str | None, industry: str | None
) -> dict[str, Any]:
    """Return ``{"recommended": [...], "explanation": "..."}`` for a sector/industry."""
    if industry and industry in INDUSTRY_OVERRIDES:
        return INDUSTRY_OVERRIDES[industry]
    return GICS_SECTOR_MULTIPLES.get(sector or "", _DEFAULT_RECOMMENDATION)


class IndustryExplainer(Protocol):
    """Hook for future LLM-backed explanations — same signature as ``static_explainer``."""

    def __call__(
        self,
        sector: str | None,
        industry: str | None,
        multiples: dict[str, float | None],
    ) -> str: ...


def static_explainer(
    sector: str | None,
    industry: str | None,
    multiples: dict[str, float | None],
) -> str:
    """Default explainer — returns the canned string from the mapping."""
    return recommended_multiples(sector, industry)["explanation"]
