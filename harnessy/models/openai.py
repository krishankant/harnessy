"""OpenAI adapter (Chat Completions). Also works with any OpenAI-compatible server,
such as Ollama, through base_url."""

from __future__ import annotations

import json
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

PROVIDER = "openai"

_FINISH_REASONS: dict[str, StopReason] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "refused",
}


# --- Week 1 exercise -------------------------------------------------------------------


def map_openai_finish_reason(reason: str | None) -> StopReason:
    """stop -> "end_turn"; tool_calls -> "tool_use"; length -> "max_tokens";
    content_filter -> "refused"; anything else (including None) -> "error"."""
    raise NotImplementedError("Week 1 exercise: map_openai_finish_reason")


def to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """One {"type": "function", "function": {"name", "description", "parameters"}} per ToolSpec."""
    raise NotImplementedError("Week 1 exercise: to_openai_tools")


def to_openai_messages(messages: list[Message], system: str | None = None) -> list[dict[str, Any]]:
    """Translate harnessy messages to Chat Completions messages.

    - If system is given, it becomes the first message: {"role": "system", "content": system}.
    - Assistant turn: {"role": "assistant", "content": text}. When text is empty, content is
      None if there are tool calls, else "". Tool calls go in "tool_calls" as
      {"id", "type": "function", "function": {"name", "arguments": json.dumps(arguments)}}.
      Omit the "tool_calls" key when there are none. Ignore m.raw entirely: this format
      has no opaque state to replay, so always rebuild.
    - User turn: one {"role": "tool", "tool_call_id", "content"} message PER tool result
      (prefix content with "ERROR: " when is_error, since there is no error flag), then a
      {"role": "user", "content": text} message if there is text.
    """
    raise NotImplementedError("Week 1 exercise: to_openai_messages")


def from_openai_response(resp: dict[str, Any]) -> ModelResponse:
    """Turn a chat.completion response (as a dict) into a ModelResponse.

    - Use the first choice. text = message["content"] or "".
    - One ToolCall per message["tool_calls"] entry. "arguments" is a JSON string: parse it
      with json.loads. If it is not valid JSON, or not a JSON object, use {"_raw": <string>}
      instead of raising.
    - Message.raw = ProviderRaw(PROVIDER, the choice's message dict).
    - stop_reason via map_openai_finish_reason(choice["finish_reason"]).
    - usage: prompt_tokens -> input_tokens, completion_tokens -> output_tokens (missing -> 0).
    - ModelResponse.raw = resp.
    """
    raise NotImplementedError("Week 1 exercise: from_openai_response")


# --- Given -----------------------------------------------------------------------------


class OpenAIModel:
    def __init__(self, model: str | None = None, client: Any | None = None, base_url: str | None = None):
        self.name = model or os.environ.get("OPENAI_MODEL") or ""
        if not self.name:
            raise ValueError("Set OPENAI_MODEL in .env to a current model that supports tool calling.")
        if client is None:
            import openai

            client = openai.OpenAI(base_url=base_url or os.environ.get("OPENAI_BASE_URL") or None)
        self._client = client

    def complete(self, messages: list[Message], tools: list[ToolSpec], system: str | None = None) -> ModelResponse:
        kwargs: dict[str, Any] = {"model": self.name, "messages": to_openai_messages(messages, system)}
        if tools:  # the API rejects an empty tools array
            kwargs["tools"] = to_openai_tools(tools)
        resp = self._client.chat.completions.create(**kwargs)
        return from_openai_response(resp.model_dump(mode="json", exclude_none=True))
