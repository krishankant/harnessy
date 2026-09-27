"""The agent loop: call the model, run the tools it asks for, repeat until it stops
or a limit is reached. The loop never raises for limits or tool failures."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

from harnessy.models.base import Model
from harnessy.types import Message, ModelResponse, ToolCall, ToolResult, ToolSpec, Usage

RunStopReason = Literal["end_turn", "max_steps", "max_tokens", "timeout", "refused", "model_error"]


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    fn: Callable[..., object]

    @property
    def name(self) -> str:
        return self.spec.name


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
        messages: list[Message] = [Message(role="user", text=task)]
        steps: list[Step] = []
        usage = Usage()
        specs = [t.spec for t in self.tools]
        start = self.clock()

        def finish(reason: RunStopReason, text: str = "", error: str | None = None) -> RunResult:
            return RunResult(text, reason, steps, usage, messages, error)

        while True:
            if len(steps) >= self.max_steps:
                return finish("max_steps")
            if usage.total >= self.max_tokens_total:
                return finish("max_tokens")
            if self.clock() - start >= self.timeout_s:
                return finish("timeout")

            try:
                response = self.model.complete(messages, specs, self.system)
            except Exception as e:  # any model failure ends the run cleanly
                return finish("model_error", error=f"{type(e).__name__}: {e}")

            usage = usage + response.usage
            messages.append(response.message)

            if response.message.tool_calls and response.stop_reason != "max_tokens":
                results = tuple(self._run_tool(call) for call in response.message.tool_calls)
                messages.append(Message(role="user", tool_results=results))
                steps.append(Step(len(steps), response, results))
                self._log(steps[-1])
                continue

            steps.append(Step(len(steps), response))
            self._log(steps[-1])
            text = response.message.text
            if response.stop_reason == "refused":
                return finish("refused", text)
            if response.stop_reason in ("error", "max_tokens"):
                return finish("model_error", text, error=f"model stopped with '{response.stop_reason}'")
            return finish("end_turn", text)

    def _run_tool(self, call: ToolCall) -> ToolResult:
        tool = self._by_name.get(call.name)
        if tool is None:
            available = ", ".join(sorted(self._by_name)) or "none"
            return ToolResult(call.id, f"Unknown tool '{call.name}'. Available tools: {available}.", is_error=True)
        try:
            output = tool.fn(**call.arguments)
        except TypeError as e:
            return ToolResult(call.id, f"Bad arguments for '{call.name}': {e}. Check the tool's parameters.", is_error=True)
        except Exception as e:
            return ToolResult(call.id, f"Tool '{call.name}' failed: {type(e).__name__}: {e}", is_error=True)
        return ToolResult(call.id, output if isinstance(output, str) else str(output))

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
