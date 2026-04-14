"""Normalized financial metric models."""

from __future__ import annotations

from pydantic import BaseModel


class AnnualMetric(BaseModel):
    """A single year's value for a financial metric."""

    calendar_year: int
    value: float
    fiscal_year: int
    filing_date: str
    sec_accession: str
    form: str


class CompanyFinancials(BaseModel):
    """Fully normalized financial dataset for one company."""

    cik: int
    ticker: str
    entity_name: str
    revenue: list[AnnualMetric] = []
    net_income: list[AnnualMetric] = []
    operating_income: list[AnnualMetric] = []
    total_assets: list[AnnualMetric] = []
    total_liabilities: list[AnnualMetric] = []
    stockholders_equity: list[AnnualMetric] = []
    operating_cash_flow: list[AnnualMetric] = []
    capital_expenditure: list[AnnualMetric] = []
    free_cash_flow: list[AnnualMetric] = []
    interest_expense: list[AnnualMetric] = []
    long_term_debt: list[AnnualMetric] = []
    cash_and_equivalents: list[AnnualMetric] = []
    diluted_eps: list[AnnualMetric] = []
    diluted_shares: list[AnnualMetric] = []
    cost_of_revenue: list[AnnualMetric] = []
