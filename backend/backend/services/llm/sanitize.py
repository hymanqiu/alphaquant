"""Input sanitization for LLM prompts (defense against prompt injection).

Strategy:
- Truncate over-long user content.
- Drop control characters (keep \\n / \\t).
- HTML-escape ``< > &`` so that tags embedded in user content cannot collide
  with any XML-style delimiters a prompt template may use.
- Wrap the content in explicit boundary markers so system prompts can instruct
  the model to treat anything inside as data.
- Log suspicious injection phrases for monitoring (does not block — the
  boundary wrapping + system prompt hardening is the real defense).
"""

from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)

USER_CONTENT_OPEN: Final[str] = "<<<USER_CONTENT>>>"
USER_CONTENT_CLOSE: Final[str] = "<<<END_USER_CONTENT>>>"

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Phrases that, while not sufficient to block, are strong signals that a model
# is being told to disregard instructions. Log for post-hoc review.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|all|above)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"(你|请)?\s*忽略\s*(之前|以上|前面|所有)?\s*(的)?\s*(指令|提示|规则)", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
]


def check_injection(text: str) -> bool:
    """Return True iff *text* contains a known injection phrase."""
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def sanitize_text(text: str, *, max_len: int = 2000) -> str:
    """Return a wrapped, safe-to-interpolate version of *text*.

    The returned string is already wrapped in boundary markers; callers should
    interpolate it directly into user prompts.
    """
    if not isinstance(text, str):
        text = str(text)

    if len(text) > max_len:
        text = text[:max_len] + "…"

    # Strip control characters (keep \n \t).
    text = _CONTROL_CHARS_RE.sub("", text)

    # HTML-escape the three delimiter chars. Escaping & first is important.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if check_injection(text):
        # Truncate to a short excerpt for the log to avoid leaking long user
        # content; the boundary wrapping remains the primary defense.
        logger.warning(
            "llm_injection_suspected pattern_detected=1 excerpt=%r",
            text[:120],
        )

    return f"{USER_CONTENT_OPEN}\n{text}\n{USER_CONTENT_CLOSE}"


def sanitize_list(texts: list[str], *, max_item_len: int = 500) -> str:
    """Sanitize a list of short text items and join them numbered.

    Each item is escaped and length-limited; the whole block is wrapped in a
    single pair of boundary markers.
    """
    cleaned: list[str] = []
    saw_injection = False
    for i, item in enumerate(texts, 1):
        s = str(item)
        if len(s) > max_item_len:
            s = s[:max_item_len] + "…"
        s = _CONTROL_CHARS_RE.sub("", s)
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if check_injection(s):
            saw_injection = True
        cleaned.append(f"[{i}] {s}")

    if saw_injection:
        logger.warning(
            "llm_injection_suspected scope=list item_count=%d",
            len(texts),
        )

    body = "\n".join(cleaned)
    return f"{USER_CONTENT_OPEN}\n{body}\n{USER_CONTENT_CLOSE}"
