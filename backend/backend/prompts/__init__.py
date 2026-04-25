"""Prompt template library.

Each prompt lives in ``<name>_v<N>.yaml`` and exposes a ``system`` block, a
``user`` format string, and tuning defaults. Templates are loaded once per
process and cached.

YAML schema (minimal):

.. code-block:: yaml

    name: investment_thesis
    version: 1
    temperature: 0.2
    max_tokens: 2500
    model_hint: deepseek-chat        # optional, informational only
    response_schema: InvestmentThesis  # optional, informational only
    system: |
      <system prompt text>
    user: |
      <user prompt with {placeholders}>
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent
_CACHE: dict[tuple[str, int], "PromptTemplate"] = {}


@dataclass(frozen=True)
class PromptTemplate:
    """Parsed prompt template."""

    name: str
    version: int
    system: str
    user: str
    temperature: float
    max_tokens: int
    model_hint: str | None = None
    response_schema: str | None = None


def _parse_template(name: str, version: int, data: dict[str, Any]) -> PromptTemplate:
    try:
        declared_name = str(data["name"])
        declared_version = int(data["version"])
        system = str(data["system"])
        user = str(data["user"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(
            f"prompt '{name}' v{version}: invalid YAML structure ({e})"
        ) from e

    if declared_name != name:
        raise ValueError(
            f"prompt file name mismatch: path '{name}' vs yaml name '{declared_name}'"
        )
    if declared_version != version:
        raise ValueError(
            f"prompt version mismatch: path v{version} vs yaml version v{declared_version}"
        )

    return PromptTemplate(
        name=name,
        version=version,
        system=system.rstrip() + "\n",
        user=user.rstrip() + "\n",
        temperature=float(data.get("temperature", 0.1)),
        max_tokens=int(data.get("max_tokens", 2000)),
        model_hint=data.get("model_hint"),
        response_schema=data.get("response_schema"),
    )


def load_prompt(name: str, version: int = 1) -> PromptTemplate:
    """Load ``<name>_v<version>.yaml`` from this directory.

    Templates are cached by (name, version). Raises ``FileNotFoundError`` or
    ``ValueError`` for malformed templates; callers can treat these as
    programming errors — bad prompts should be caught at startup.
    """
    key = (name, version)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    path = _PROMPTS_DIR / f"{name}_v{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"prompt '{name}' v{version}: YAML root must be a mapping")

    template = _parse_template(name, version, data)
    _CACHE[key] = template
    return template


def clear_prompt_cache() -> None:
    """Drop the in-process cache. Useful in tests / dev reload scenarios."""
    _CACHE.clear()


def list_available_prompts() -> list[tuple[str, int]]:
    """List ``(name, version)`` pairs available on disk."""
    result: list[tuple[str, int]] = []
    for path in _PROMPTS_DIR.glob("*_v*.yaml"):
        stem = path.stem  # e.g. "sentiment_v1"
        if "_v" not in stem:
            continue
        name, _, ver = stem.rpartition("_v")
        try:
            result.append((name, int(ver)))
        except ValueError:
            continue
    return sorted(result)


__all__ = [
    "PromptTemplate",
    "clear_prompt_cache",
    "list_available_prompts",
    "load_prompt",
]
