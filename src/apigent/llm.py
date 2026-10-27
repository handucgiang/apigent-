"""LLM adapters.

v0.1 speaks the OpenAI-compatible chat-completions protocol, which covers
OpenAI, Groq, Gemini, Anthropic (compat endpoint), OpenRouter, Ollama, vLLM
and most self-hosted servers. Pick one with ``"<provider>/<model>"``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

PROVIDERS: dict[str, tuple[str, str | None]] = {
    # prefix: (base_url, api-key env var)
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    def as_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.name,
                        "arguments": c.raw_arguments or json.dumps(c.arguments, ensure_ascii=False),
                    },
                }
                for c in self.tool_calls
            ]
        return msg


class LLM(Protocol):
    async def complete(
        self, messages: Sequence[dict[str, Any]], tools: Sequence[dict[str, Any]]
    ) -> LLMResponse: ...


class LLMError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def complete(
        self, messages: Sequence[dict[str, Any]], tools: Sequence[dict[str, Any]]
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = list(tools)
            body["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = await self._client.post(
            f"{self.base_url}/chat/completions", json=body, headers=headers
        )
        if resp.status_code >= 400:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        msg = data["choices"][0]["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            raw = c["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                args = {"_invalid_json": raw}
            calls.append(
                ToolCall(
                    id=c["id"],
                    name=c["function"]["name"],
                    arguments=args,
                    raw_arguments=raw if isinstance(raw, str) else "",
                )
            )
        return LLMResponse(
            content=msg.get("content"), tool_calls=calls, usage=data.get("usage", {})
        )


def make_llm(spec: str | LLM, **kwargs: Any) -> LLM:
    """Build an LLM from ``"provider/model"`` (e.g. ``"groq/openai/gpt-oss-120b"``)."""
    if not isinstance(spec, str):
        return spec
    provider, _, model = spec.partition("/")
    if provider not in PROVIDERS or not model:
        raise ValueError(
            f"Unknown LLM spec {spec!r}. Use '<provider>/<model>' with provider in "
            f"{sorted(PROVIDERS)} or pass an LLM instance."
        )
    base_url, key_env = PROVIDERS[provider]
    base_url = kwargs.pop("base_url", None) or os.getenv(f"{provider.upper()}_BASE_URL", base_url)
    api_key = kwargs.pop("api_key", None) or (os.getenv(key_env) if key_env else None)
    return OpenAICompatibleLLM(model=model, base_url=base_url, api_key=api_key, **kwargs)


class ScriptedLLM:
    """Deterministic LLM for tests: returns the given responses in order."""

    def __init__(self, responses: Sequence[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    async def complete(
        self, messages: Sequence[dict[str, Any]], tools: Sequence[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append((list(messages), list(tools)))
        if not self._responses:
            raise LLMError("ScriptedLLM ran out of responses")
        return self._responses.pop(0)
