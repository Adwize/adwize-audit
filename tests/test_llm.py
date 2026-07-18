"""Reasoning models (o3, o4-mini, …) reject a custom temperature; the shared
helper must drop it and retry so any model works."""

from types import SimpleNamespace

import openai
import pytest

from agents import llm


class _FakeBadRequestError(Exception):
    pass


def _msg(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_retries_without_temperature(monkeypatch):
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            if "temperature" in kwargs:
                raise _FakeBadRequestError("Unsupported value: 'temperature' ... only default (1)")
            return _msg("ok")

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "BadRequestError", _FakeBadRequestError)
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda: FakeClient())

    text = await llm.complete("o3", [{"role": "user", "content": "hi"}], temperature=0.2)

    assert text == "ok"
    assert len(calls) == 2  # first with temperature (fails), retry without
    assert "temperature" in calls[0] and "temperature" not in calls[1]


@pytest.mark.asyncio
async def test_no_retry_when_temperature_ok(monkeypatch):
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return _msg("fine")

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "BadRequestError", _FakeBadRequestError)
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda: FakeClient())

    text = await llm.complete("gpt-4o", [{"role": "user", "content": "hi"}], temperature=0.2)
    assert text == "fine"
    assert len(calls) == 1
