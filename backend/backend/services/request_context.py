"""Per-request context — currently just the client IP.

Why ``contextvars``: requests run through many async layers (FastAPI route →
LangGraph node → LLM client). Threading the IP through every function signature
would be invasive; a ``ContextVar`` propagates automatically across ``await``
and is correctly isolated between concurrent requests.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from fastapi import Request

_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)


def extract_client_ip(request: Request) -> str:
    """Return the best-guess client IP for *request*.

    Honors ``X-Forwarded-For`` (first hop) when present — useful behind a
    proxy — and falls back to the raw socket peer. Returns ``"unknown"`` when
    the socket info is unavailable (e.g. under the TestClient).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    client = request.client
    if client and client.host:
        return client.host
    return "unknown"


@contextmanager
def bind_client_ip(ip: str) -> Iterator[None]:
    """Context manager that sets the client IP for the duration of a block."""
    token = _client_ip.set(ip)
    try:
        yield
    finally:
        _client_ip.reset(token)


def current_client_ip() -> str | None:
    """Return the IP bound to the current async context, if any."""
    return _client_ip.get()
