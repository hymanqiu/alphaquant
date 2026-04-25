"""Shared LLM infrastructure: single entry point for all LLM calls.

All LLM-using code should go through ``get_llm_client()``. The client handles
prompt loading, input sanitization, retries, structured output parsing, and
token accounting.
"""

from .accounting import AccountingStore, LLMUsageRecord
from .budget import BudgetGate
from .client import (
    LLMClient,
    close_llm_client,
    get_accounting_store,
    get_llm_client,
    is_llm_configured,
)
from .errors import (
    LLMBudgetExceeded,
    LLMConfigError,
    LLMError,
    LLMParseError,
    LLMProviderError,
)
from .sanitize import check_injection, sanitize_list, sanitize_text

__all__ = [
    "AccountingStore",
    "BudgetGate",
    "LLMBudgetExceeded",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMParseError",
    "LLMProviderError",
    "LLMUsageRecord",
    "check_injection",
    "close_llm_client",
    "get_accounting_store",
    "get_llm_client",
    "is_llm_configured",
    "sanitize_list",
    "sanitize_text",
]
