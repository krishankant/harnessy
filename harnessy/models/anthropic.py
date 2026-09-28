"""Anthropic adapter: translates harnessy types to the Messages API and back."""

from __future__ import annotations

import os
from typing import Any

from harnessy.types import (
    Message,
    ModelResponse,
    ProviderRaw,
    StopReason,
    ToolCall,
    ToolSpec,
    Usage,
)

PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-5"
# Models that accept server-side refusal fallbacks ("default" routes by refusal category).
FALLBACK_MODELS = frozenset({"claude-opus-5", "claude-fable-5-1"})
MAX_TOKENS = 16000

_STOP_REASONS: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refused",
}


# --- Week 1 exercise -------------------------------------------------------------------


def map_anthropic_stop_reason(reason: str | None) -> StopReason:
    """Map an Anthropic stop_reason to harnessy's StopReason.

    end_turn and stop_sequence -> "end_turn"; tool_use -> "tool_use";
    max_tokens -> "max_tokens"; refusal -> "refused"; anything else (including None) -> "error".
    Hint: the _STOP_REASONS table above is already written for you.
    """
    raise NotImplementedError("Week 1 exercise: map_anthropic_stop_reason")


def to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Return one {"name", "description", "input_schema"} dict per ToolSpec."""
    raise NotImplementedError("Week 1 exercise: to_anthropic_tools")


def to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate harnessy messages to Anthropic's {"role", "content": [blocks]} format.

    Assistant turns:
      - if m.raw is not None and m.raw.provider == PROVIDER: send m.raw.content unchanged
        (it may hold thinking blocks the API needs back exactly as they were);
      - otherwise build blocks: a text block if m.text, then one tool_use block
        {"type": "tool_use", "id", "name", "input"} per tool call; if that leaves no
        blocks, send one text block "(no output)".
    User turns:
      - tool_result blocks first, one per result:
        {"type": "tool_result", "tool_use_id", "content", "is_error"};
      - then a text block if m.text.
    """
    raise NotImplementedError("Week 1 exercise: to_anthropic_messages")


def from_anthropic_response(resp: dict[str, Any]) -> ModelResponse:
    """Turn a Messages API response (as a dict) into a ModelResponse.

    - text: concatenate the "text" of every text block, in order, with no separator;
    - tool_calls: a ToolCall(id, name, input or {}) per tool_use block, in order;
    - ignore every other block type for text/tool_calls (thinking, fallback, ...),
      but keep ALL of resp["content"] in Message.raw = ProviderRaw(PROVIDER, content);
    - stop_reason via map_anthropic_stop_reason; usage from resp["usage"] (missing -> 0);
    - ModelResponse.raw = resp.
    """
    raise NotImplementedError("Week 1 exercise: from_anthropic_response")


# --- Given -----------------------------------------------------------------------------


class AnthropicModel:
    def __init__(self, model: str | None = None, client: Any | None = None, max_tokens: int = MAX_TOKENS):
        self.name = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self.max_tokens = max_tokens

    def _request(self, messages: list[Message], tools: list[ToolSpec], system: str | None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.name,
            "max_tokens": self.max_tokens,
            "messages": to_anthropic_messages(messages),
        }
        if tools:
            kwargs["tools"] = to_anthropic_tools(tools)
        if system:
            kwargs["system"] = system
        if self.name in FALLBACK_MODELS:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["extra_body"] = {"fallbacks": "default"}
        return kwargs

    def complete(self, messages: list[Message], tools: list[ToolSpec], system: str | None = None) -> ModelResponse:
        resp = self._client.beta.messages.create(**self._request(messages, tools, system))
        return from_anthropic_response(resp.model_dump(mode="json", by_alias=True, exclude_none=True))

    def stream(self, messages: list[Message], tools: list[ToolSpec], system: str | None = None):
        """Yield text chunks as they arrive, then the ModelResponse (week 7)."""
        with self._client.beta.messages.stream(**self._request(messages, tools, system)) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
        yield from_anthropic_response(final.model_dump(mode="json", by_alias=True, exclude_none=True))
