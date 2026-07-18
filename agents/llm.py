"""Thin OpenAI chat helper shared by agents.

Handles the annoying model-capability differences transparently: reasoning
models (o3, o4-mini, …) reject a custom `temperature`, so if the API complains
about an unsupported temperature we retry once without it. This keeps agents
model-agnostic — set any model per agent and it just works.
"""

from __future__ import annotations

from typing import Any


async def complete(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    response_format: dict[str, Any] | None = None,
    timeout: float = 60,
) -> str:
    """Return the assistant message text. Raises on genuine API errors."""
    from openai import AsyncOpenAI, BadRequestError

    client = AsyncOpenAI()
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "timeout": timeout}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if response_format is not None:
        kwargs["response_format"] = response_format

    try:
        resp = await client.chat.completions.create(**kwargs)
    except BadRequestError as exc:
        # reasoning models only accept the default temperature — drop it and retry
        if "temperature" in str(exc) and "temperature" in kwargs:
            kwargs.pop("temperature")
            resp = await client.chat.completions.create(**kwargs)
        else:
            raise
    return resp.choices[0].message.content or ""
