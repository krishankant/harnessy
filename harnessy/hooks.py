"""Hooks (week 6): points in the loop where your code can watch, change or block what happens,
without editing the loop itself.

Return None from any hook method to change nothing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable

from harnessy.types import Message, ModelResponse, ToolCall, ToolResult

if TYPE_CHECKING:
    from harnessy.loop import RunResult


@dataclass(frozen=True)
class Block:
    """Returned by before_model or before_tool to stop that call, with a reason."""

    reason: str


# --- Given -----------------------------------------------------------------------------


class Hook:
    """Override only the methods you need. Every default does nothing and returns None."""

    def on_start(self, agent: Any, task: str) -> None:
        """A run is starting."""

    def before_model(self, view: list[Message]) -> list[Message] | Block | None:
        """Return a changed view, a Block to end the run ("blocked"), or None."""

    def after_model(self, response: ModelResponse) -> ModelResponse | None:
        """Return a changed response, or None."""

    def before_tool(self, call: ToolCall) -> ToolCall | Block | None:
        """Return a changed call, a Block (the model gets the reason as an error result), or None."""

    def after_tool(self, call: ToolCall, result: ToolResult) -> ToolResult | None:
        """Return a changed result, or None."""

    def on_stop(self, result: RunResult) -> str | None:
        """The model says it's done. Return a message to send it back to work, or None to accept."""

    def on_finish(self, result: RunResult) -> None:
        """The run has ended, however it ended. Observe only."""


class StopCheck(Hook):
    """Reject "done" while check(result) returns a message, at most max_rejections times per run."""

    def __init__(self, check: Callable[[Any], str | None], max_rejections: int = 2):
        self.check = check
        self.max_rejections = max_rejections
        self.rejections = 0

    def on_start(self, agent: Any, task: str) -> None:
        self.rejections = 0

    def on_stop(self, result: Any) -> str | None:
        if self.rejections >= self.max_rejections:
            return None
        message = self.check(result)
        if message:
            self.rejections += 1
        return message


class HookRunner:
    """Runs a list of hooks in order at each hook point."""

    def __init__(self, hooks: Iterable[Hook]):
        self.hooks = list(hooks)

    def on_start(self, agent: Any, task: str) -> None:
        for hook in self.hooks:
            hook.on_start(agent, task)

    def on_finish(self, result: Any) -> None:
        for hook in self.hooks:
            hook.on_finish(result)

    # --- Week 6 exercise ---

    def before_model(self, view: list[Message]) -> list[Message] | Block:
        """Pass the view through each hook in order: a hook returning None keeps the current
        view, a list replaces it for the next hook, and the first Block is returned at once
        (later hooks don't run). Return the final view."""
        raise NotImplementedError("Week 6 exercise: HookRunner.before_model")

    def after_model(self, response: ModelResponse) -> ModelResponse:
        """Same chaining, without Block."""
        raise NotImplementedError("Week 6 exercise: HookRunner.after_model")

    def before_tool(self, call: ToolCall) -> ToolCall | Block:
        """Same chaining as before_model, for one tool call."""
        raise NotImplementedError("Week 6 exercise: HookRunner.before_tool")

    def after_tool(self, call: ToolCall, result: ToolResult) -> ToolResult:
        """Same chaining as after_model, for one tool result (each hook also gets the call)."""
        raise NotImplementedError("Week 6 exercise: HookRunner.after_tool")

    def on_stop(self, result: Any) -> str | None:
        """The first hook that returns a message wins; None if no hook objects."""
        raise NotImplementedError("Week 6 exercise: HookRunner.on_stop")
