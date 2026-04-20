"""Unit tests for industry → recommended multiples mapping."""

from __future__ import annotations

from backend.agents.nodes.industry_mapping import (
    recommended_multiples,
    static_explainer,
)


def test_real_estate_recommends_p_ffo() -> None:
    result = recommended_multiples("Real Estate", None)
    assert "p_ffo" in result["recommended"]
    assert "REIT" in result["explanation"] or "FFO" in result["explanation"]


def test_utilities_recommends_dividend_yield() -> None:
    result = recommended_multiples("Utilities", None)
    assert "dividend_yield" in result["recommended"]
    assert "pe" in result["recommended"]


def test_financials_default_is_pe_pb() -> None:
    result = recommended_multiples("Financials", None)
    assert result["recommended"] == ["pe", "pb"]


def test_insurance_industry_override() -> None:
    """INDUSTRY_OVERRIDES should win over GICS_SECTOR_MULTIPLES."""
    result = recommended_multiples("Financials", "Insurance")
    assert result["recommended"] == ["pb", "pe"]
    assert "book value" in result["explanation"].lower()


def test_asset_management_override_removes_pb() -> None:
    result = recommended_multiples("Financials", "Asset Management")
    assert "pb" not in result["recommended"]
    assert "pe" in result["recommended"]


def test_unknown_sector_returns_default() -> None:
    result = recommended_multiples(None, None)
    assert set(result["recommended"]) == {
        "pe", "pb", "ps", "ev_to_revenue", "ev_to_ebit", "ev_to_fcf",
    }
    assert "unclassified" in result["explanation"].lower()


def test_fmp_technology_label_is_supported() -> None:
    """FMP uses 'Technology' not GICS 'Information Technology' — both should work."""
    from_gics = recommended_multiples("Information Technology", None)
    from_fmp = recommended_multiples("Technology", None)
    assert from_gics["recommended"] == from_fmp["recommended"]


def test_static_explainer_returns_mapping_text() -> None:
    text = static_explainer("Real Estate", None, {})
    assert text == recommended_multiples("Real Estate", None)["explanation"]
