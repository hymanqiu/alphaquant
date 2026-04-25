"""10-K section extraction.

Strategy: flatten the HTML to plain text, then use tiered regex patterns to
locate Item boundaries. We always pick the **last** match of the start
pattern, which naturally skips the table-of-contents references at the top of
the document.

Only Item 7 (Management's Discussion & Analysis) is extracted in this phase.
Risk factors / business description can reuse the same boundary logic in a
follow-up.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PARSER_VERSION = 1

_MIN_SECTION_CHARS = 2_000
_MAX_SECTION_CHARS = 80_000


@dataclass(frozen=True)
class ExtractedSection:
    """A single section extracted from a 10-K."""

    name: str               # e.g. "mdna"
    text: str
    char_count: int
    strategy: str           # which tier of the regex cascade hit
    parser_version: int = PARSER_VERSION


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def html_to_text(html: str) -> str:
    """Strip scripts/styles and flatten to plain text with newline separators."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Use newline separator so Item boundaries remain locatable line-by-line,
    # and collapse to plain text.
    return soup.get_text("\n", strip=True)


# ---------------------------------------------------------------------------
# MD&A extraction (Item 7 → next Item 7A / Item 8)
# ---------------------------------------------------------------------------

# Tier 1: strict — "Item 7." + 2+ whitespace + Management's Discussion. This
# discriminates the real section from the single-space ToC entries used in
# Apple/MSFT/Google-style filings.
_MDNA_STRICT = re.compile(
    r"Item\s+7[\.\s]{2,}Management[’'']s\s+Discussion\s+and\s+Analysis",
    re.IGNORECASE,
)

# Tier 2: loose — any whitespace. Pick the last match (naturally skips the ToC).
_MDNA_LOOSE = re.compile(
    r"Item\s+7[\.\s]+Management[’'']s\s+Discussion\s+and\s+Analysis",
    re.IGNORECASE,
)

# Tier 3: very loose — some older filings use "Management Discussion" without
# the possessive apostrophe, or break the phrase across a newline/tag.
_MDNA_FALLBACK = re.compile(
    r"Item\s+7[\.\s]+(?:[’'']s\s+)?Management[’'']?s?\s+Discussion",
    re.IGNORECASE,
)

# End boundary: Item 7A (Quantitative and Qualitative Disclosures) or Item 8
# (Financial Statements). The first one after the start position wins.
_MDNA_END = re.compile(
    r"Item\s+7A[\.\s]+Quantitative|Item\s+8[\.\s]+Financial\s+Statements",
    re.IGNORECASE,
)

# --- Item 1 (Business) ---

_BUSINESS_STRICT = re.compile(
    r"Item\s+1[\.\s]{2,}Business\b",
    re.IGNORECASE,
)
_BUSINESS_LOOSE = re.compile(
    r"Item\s+1[\.\s]+Business\b",
    re.IGNORECASE,
)
# Item 1 ends at Item 1A (Risk Factors). The "1A" subsection is always next.
_BUSINESS_END = re.compile(
    r"Item\s+1A[\.\s]+Risk\s+Factors",
    re.IGNORECASE,
)


# --- Item 1A (Risk Factors) ---

# Tier 1: strict — Item 1A. + 2+ whitespace + Risk Factors
_RISK_STRICT = re.compile(
    r"Item\s+1A[\.\s]{2,}Risk\s+Factors",
    re.IGNORECASE,
)
# Tier 2: any whitespace (pick last occurrence, skipping ToC)
_RISK_LOOSE = re.compile(
    r"Item\s+1A[\.\s]+Risk\s+Factors",
    re.IGNORECASE,
)

# End boundary: Item 1B (Unresolved Staff Comments) or Item 2 (Properties).
# Whichever appears first after the start wins.
_RISK_END = re.compile(
    r"Item\s+1B[\.\s]+Unresolved|Item\s+2[\.\s]+Properties",
    re.IGNORECASE,
)


def _find_last(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    """Return the last regex match in *text* or None."""
    last: re.Match[str] | None = None
    for m in pattern.finditer(text):
        last = m
    return last


def extract_mdna(html: str) -> ExtractedSection | None:
    """Extract Management's Discussion and Analysis from a 10-K.

    Returns ``None`` when no section could be reliably isolated. Callers
    should gracefully degrade on ``None``.
    """
    text = html_to_text(html)
    if len(text) < 5_000:
        logger.info("tenk_parser: text too short (%d chars), skipping", len(text))
        return None

    # Cascade: prefer strict, fall back to looser patterns.
    for strategy, pattern in [
        ("strict_multi_ws", _MDNA_STRICT),
        ("loose_any_ws", _MDNA_LOOSE),
        ("fallback_loose", _MDNA_FALLBACK),
    ]:
        match = _find_last(pattern, text)
        if match is None:
            continue

        start = match.start()
        # Search for the end boundary starting from just after the header,
        # so we don't grab the end marker that preceded this start.
        end_match = _MDNA_END.search(text, pos=match.end())
        if end_match is not None:
            end = end_match.start()
        else:
            end = min(start + _MAX_SECTION_CHARS, len(text))

        section = text[start:end].strip()
        if len(section) < _MIN_SECTION_CHARS:
            logger.info(
                "tenk_parser: %s matched but section too short (%d chars); trying next tier",
                strategy, len(section),
            )
            continue
        if len(section) > _MAX_SECTION_CHARS:
            section = section[:_MAX_SECTION_CHARS]

        logger.info(
            "tenk_parser: MD&A extracted via %s (%d chars, start=%d, end=%d)",
            strategy, len(section), start, end,
        )
        return ExtractedSection(
            name="mdna",
            text=section,
            char_count=len(section),
            strategy=strategy,
        )

    logger.info("tenk_parser: MD&A not found by any strategy")
    return None


# ---------------------------------------------------------------------------
# Risk Factors extraction (Item 1A → Item 1B / Item 2)
# ---------------------------------------------------------------------------


def extract_risk_factors(html: str) -> ExtractedSection | None:
    """Extract Item 1A Risk Factors from a 10-K.

    Returns ``None`` when the section can't be reliably isolated. Callers
    should degrade gracefully on ``None``.
    """
    text = html_to_text(html)
    if len(text) < 5_000:
        logger.info("tenk_parser: text too short (%d chars), skipping", len(text))
        return None

    for strategy, pattern in [
        ("strict_multi_ws", _RISK_STRICT),
        ("loose_any_ws", _RISK_LOOSE),
    ]:
        match = _find_last(pattern, text)
        if match is None:
            continue

        start = match.start()
        end_match = _RISK_END.search(text, pos=match.end())
        if end_match is not None:
            end = end_match.start()
        else:
            # Risk Factors can run very long; fall back to max cap.
            end = min(start + _MAX_SECTION_CHARS, len(text))

        section = text[start:end].strip()
        if len(section) < _MIN_SECTION_CHARS:
            logger.info(
                "tenk_parser: %s matched but Risk Factors too short (%d chars); trying next tier",
                strategy, len(section),
            )
            continue
        if len(section) > _MAX_SECTION_CHARS:
            section = section[:_MAX_SECTION_CHARS]

        logger.info(
            "tenk_parser: Risk Factors extracted via %s (%d chars, start=%d, end=%d)",
            strategy, len(section), start, end,
        )
        return ExtractedSection(
            name="risk_factors",
            text=section,
            char_count=len(section),
            strategy=strategy,
        )

    logger.info("tenk_parser: Risk Factors not found by any strategy")
    return None


# ---------------------------------------------------------------------------
# Item 1 Business extraction (Item 1 → Item 1A)
# ---------------------------------------------------------------------------


def extract_business(html: str) -> ExtractedSection | None:
    """Extract the Item 1 Business section from a 10-K.

    Returns ``None`` when the section cannot be reliably isolated. The
    Business section is the source of truth for moat / competitive-position
    analysis: company strategy, segments, products, distribution, suppliers.
    """
    text = html_to_text(html)
    if len(text) < 5_000:
        logger.info("tenk_parser: text too short (%d chars), skipping Business", len(text))
        return None

    for strategy, pattern in [
        ("strict_multi_ws", _BUSINESS_STRICT),
        ("loose_any_ws", _BUSINESS_LOOSE),
    ]:
        match = _find_last(pattern, text)
        if match is None:
            continue

        start = match.start()
        end_match = _BUSINESS_END.search(text, pos=match.end())
        if end_match is not None:
            end = end_match.start()
        else:
            end = min(start + _MAX_SECTION_CHARS, len(text))

        section = text[start:end].strip()
        if len(section) < _MIN_SECTION_CHARS:
            logger.info(
                "tenk_parser: %s matched Business but section too short (%d chars)",
                strategy, len(section),
            )
            continue
        if len(section) > _MAX_SECTION_CHARS:
            section = section[:_MAX_SECTION_CHARS]

        logger.info(
            "tenk_parser: Business extracted via %s (%d chars, start=%d, end=%d)",
            strategy, len(section), start, end,
        )
        return ExtractedSection(
            name="business",
            text=section,
            char_count=len(section),
            strategy=strategy,
        )

    logger.info("tenk_parser: Business not found by any strategy")
    return None


# ---------------------------------------------------------------------------
# Smart truncation for LLM prompts (head + tail)
# ---------------------------------------------------------------------------


def smart_truncate(text: str, *, max_chars: int = 12_000) -> str:
    """Return *text* unchanged if short enough, else head + tail with marker.

    MD&A in 10-Ks is structured: Overview → Results → Liquidity → Critical
    Accounting. XBRL already captures the numeric Results portion, so when we
    must cut, preferring head + tail keeps the most LLM-useful content
    (forward-looking tone + liquidity / critical accounting estimates) while
    dropping the middle (numeric tables the LLM shouldn't need).
    """
    if len(text) <= max_chars:
        return text

    head_budget = max_chars // 2
    tail_budget = max_chars - head_budget - 100  # leave room for the marker
    head = text[:head_budget].rstrip()
    tail = text[-tail_budget:].lstrip()
    return (
        head
        + "\n\n[...truncated numeric/tabular middle; content continues below...]\n\n"
        + tail
    )


def truncate_head(text: str, *, max_chars: int = 16_000) -> str:
    """Keep only the leading *max_chars* characters.

    10-K Risk Factors sections list individual risks roughly in priority
    order — head-only truncation preserves the most material risks while
    dropping boilerplate repetition further down.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[...truncated — list continues with additional lower-priority risks...]"
