"""Streaming for the OpenAI adapter (week 7): tool calls arrive in fragments, spread over many
chunks. Put them back together into the same dict a non-streaming call returns."""

from __future__ import annotations

from typing import Any

# --- Week 7 exercise -------------------------------------------------------------------


def merge_openai_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild a non-streaming Chat Completions response from streamed chunks, so
    from_openai_response can parse it unchanged:

    {"id": <first chunk's id>, "model": <first chunk's model>,
     "choices": [{"index": 0, "message": {...}, "finish_reason": <last non-null finish_reason>}],
     "usage": <the chunk that has usage, else {}>}

    message: {"role": "assistant", "content": <all delta content joined, or None if there was
    none>, "tool_calls": [...]} — leave the "tool_calls" key out if there were none.
    Tool calls arrive as fragments keyed by "index": keep the first id, type and function name
    seen for each index, and concatenate the function "arguments" fragments in order. Output
    them sorted by index, each as {"id", "type", "function": {"name", "arguments"}}.
    A chunk may have an empty "choices" list (the usage chunk).
    """
    raise NotImplementedError("Week 7 exercise: merge_openai_chunks")
