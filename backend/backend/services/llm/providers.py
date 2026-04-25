"""LLM provider adapters.

Only the DeepSeek / OpenAI-compatible provider is implemented in this phase.
A Claude adapter can be added later by implementing the same ``Provider``
protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .errors import LLMConfigError, LLMProviderError


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized response across providers.

    ``content`` is always a raw string — JSON parsing lives in ``LLMClient``.
    """

    content: str
    input_tokens: int
    output_tokens: int
    raw: dict[str, Any]


class Provider(Protocol):
    name: str
    model: str

    async def chat_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> ProviderResponse: ...


def _validate_base_url(url: str) -> bool:
    """Ensure the LLM base URL uses HTTPS (or localhost for dev)."""
    if url.startswith("https://"):
        return True
    return url.startswith("http://localhost") or url.startswith("http://127.0.0.1")


class OpenAICompatibleProvider:
    """OpenAI chat-completions protocol (used by DeepSeek, OpenAI, most Chinese
    vendors). All calls share a single httpx.AsyncClient."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        if not api_key:
            raise LLMConfigError(f"{name}: api_key is empty")
        if not base_url:
            raise LLMConfigError(f"{name}: base_url is empty")
        if not _validate_base_url(base_url):
            raise LLMConfigError(
                f"{name}: base_url must use https:// (got {base_url})"
            )
        self.name = name
        self.model = model or "deepseek-chat"
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    async def chat_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        response_format_json: bool,
    ) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = await self._http.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(
                f"{self.name} HTTP {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise LLMProviderError(f"{self.name} request error: {e}") from e
        except ValueError as e:  # JSON decode of the outer envelope
            raise LLMProviderError(f"{self.name} invalid response envelope: {e}") from e

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMProviderError(
                f"{self.name} unexpected response shape: {e}"
            ) from e

        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)

        return ProviderResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=data,
        )
