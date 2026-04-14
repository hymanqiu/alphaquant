"""Pydantic models for raw SEC EDGAR API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SECFactEntry(BaseModel):
    start: str | None = None
    end: str
    val: int | float
    accn: str
    fy: int | None = None
    fp: str | None = None
    form: str
    filed: str
    frame: str | None = None


class SECFactUnits(BaseModel):
    USD: list[SECFactEntry] | None = None
    USD_per_shares: list[SECFactEntry] | None = Field(None, alias="USD/shares")
    shares: list[SECFactEntry] | None = None
    pure: list[SECFactEntry] | None = None


class SECFact(BaseModel):
    label: str | None = None
    description: str | None = None
    units: SECFactUnits


class SECCompanyFacts(BaseModel):
    cik: int
    entityName: str
    facts: dict[str, dict[str, SECFact]]
