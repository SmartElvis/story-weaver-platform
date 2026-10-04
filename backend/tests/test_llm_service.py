"""Tests for LLMService retry behavior and Retry-After parsing.

Uses httpx.MockTransport injected into the module-level client pool so no real
network calls are made. Sleeps are stubbed to keep the suite fast.
"""

import httpx
import pytest

from app.services import llm_service
from app.services.llm_service import LLMService, _retry_after_seconds


def _make_service() -> LLMService:
    return LLMService(base_url="http://llm.test", api_key="k", model="m")


def _install_transport(monkeypatch, handler) -> None:
    """Point the shared client pool at a MockTransport and disable sleeps."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setitem(llm_service._CLIENT_POOL, ("http://llm.test", "k"), client)
    monkeypatch.setattr(llm_service.asyncio, "sleep", lambda *_: _sleep_noop())


async def _sleep_noop():
    return None


def _ok_body() -> dict:
    return {"choices": [{"message": {"content": "hello"}}], "usage": {}}


async def test_chat_returns_content_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_body())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    key = ("http://llm.test", "k")
    original = llm_service._CLIENT_POOL.get(key)
    llm_service._CLIENT_POOL[key] = client
    try:
        result = await _make_service().chat([{"role": "user", "content": "hi"}])
    finally:
        if original is None:
            llm_service._CLIENT_POOL.pop(key, None)
        else:
            llm_service._CLIENT_POOL[key] = original
    assert result == "hello"


async def test_chat_retries_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=_ok_body())

    _install_transport(monkeypatch, handler)
    result = await _make_service().chat([{"role": "user", "content": "hi"}])
    assert result == "hello"
    assert calls["n"] == 2


async def test_chat_retries_on_500_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json=_ok_body())

    _install_transport(monkeypatch, handler)
    result = await _make_service().chat([{"role": "user", "content": "hi"}])
    assert result == "hello"
    assert calls["n"] == 3


async def test_chat_raises_after_exhausting_retries(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _install_transport(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        await _make_service().chat([{"role": "user", "content": "hi"}])


async def test_chat_does_not_retry_on_400(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400)

    _install_transport(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        await _make_service().chat([{"role": "user", "content": "hi"}])
    assert calls["n"] == 1


def test_retry_after_seconds_parses_valid_values():
    resp = httpx.Response(429, headers={"Retry-After": "3"})
    assert _retry_after_seconds(resp) == 3.0


def test_retry_after_seconds_returns_none_when_absent_or_invalid():
    assert _retry_after_seconds(httpx.Response(429)) is None
    bad = httpx.Response(429, headers={"Retry-After": "soon"})
    assert _retry_after_seconds(bad) is None
    negative = httpx.Response(429, headers={"Retry-After": "-5"})
    assert _retry_after_seconds(negative) is None
