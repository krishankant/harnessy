"""The agent loop: call the model, run the tools it asks for, repeat until it stops
or a limit is reached. The loop never raises for limits or tool failures."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

from harnessy.models.base import Model
from harnessy.types import Message, ModelResponse, Tool, ToolCall, ToolResult, ToolSpec, Usage

RunStopReason = Literal["end_turn", "max_steps", "max_tokens", "timeout", "refused", "model_error"]


@dataclass(frozen=True)
class Step:
    index: int
    response: ModelResponse
    tool_results: tuple[ToolResult, ...] = ()


@dataclass
class RunResult:
    final_text: str
    stop_reason: RunStopReason
    steps: list[Step]
    usage: Usage
    messages: list[Message]
    error: str | None = None


@dataclass
class Agent:
    model: Model
    tools: list[Tool] | tuple[Tool, ...] = ()
    system: str | None = None
    max_steps: int = 10
    max_tokens_total: int = 100_000
    timeout_s: float = 120.0
    clock: Callable[[], float] = time.monotonic
    verbose: bool = False
    printer: Callable[[str], object] = print
    _by_name: dict[str, Tool] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_name = {t.name: t for t in self.tools}

    # --- Week 2 exercise ---------------------------------------------------------------


    def run(self, task: str) -> RunResult:
        """Run the agent on one task and return a RunResult. Never raises.

        1. Start with messages = [Message(role="user", text=task)], no steps, Usage().
           Record start = self.clock().
        2. Before EVERY model call, check the limits in this order and stop if one is hit:
           len(steps) >= self.max_steps       -> "max_steps"
           usage.total >= self.max_tokens_total -> "max_tokens"
           self.clock() - start >= self.timeout_s -> "timeout"
        3. Call self.model.complete(messages, [t.spec for t in self.tools], self.system).
           If it raises, stop with "model_error" and error=f"{type(e).__name__}: {e}".
        4. Add response.usage to usage and append response.message to messages.
        5. If the message has tool calls AND response.stop_reason is not "max_tokens",
           "error" or "refused" (a cut-off, failed or refused reply may hold a half-written
           call, which must not run): run each call with self._run_tool, in order;
           append ONE Message(role="user", tool_results=<all results>); record
           Step(len(steps), response, results); call self._log(step); go back to 2.
        6. Otherwise record Step(len(steps), response), call self._log(step), and stop:
           stop_reason "refused" -> "refused"; "error" or "max_tokens" -> "model_error";
           anything else -> "end_turn". final_text is the message text.
        """
        raise NotImplementedError("Week 2 exercise: Agent.run")

    def _run_tool(self, call: ToolCall) -> ToolResult:
        """Run one tool call and ALWAYS return a ToolResult with tool_call_id=call.id.

        - Unknown tool name -> is_error=True, and say which tools exist.
        - Calling tool.fn(**call.arguments) raises TypeError -> is_error=True, "Bad arguments ...".
        - Any other exception -> is_error=True, include the exception type and message.
        - Success -> content is the output, converted with str() if it is not already a str.
        """
        raise NotImplementedError("Week 2 exercise: Agent._run_tool")


    # --- Given -------------------------------------------------------------------------

    def _log(self, step: Step) -> None:
        if not self.verbose:
            return
        r = step.response
        calls = ", ".join(f"{c.name}({c.arguments})" for c in r.message.tool_calls) or "-"
        text = r.message.text.replace("\n", " ")
        if len(text) > 80:
            text = text[:77] + "..."
        self.printer(
            f"[step {step.index}] stop={r.stop_reason} tokens={r.usage.input_tokens}/{r.usage.output_tokens} "
            f"calls={calls} text={text!r}"
        )
        for res in step.tool_results:
            flag = "ERROR " if res.is_error else ""
            self.printer(f"    -> {res.tool_call_id}: {flag}{res.content[:80]}")
