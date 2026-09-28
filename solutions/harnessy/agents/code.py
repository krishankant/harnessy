"""The code agent (week 8): fixes a bug in a small repo until its tests pass."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from harnessy.hooks import StopCheck
from harnessy.loop import Agent
from harnessy.models.base import Model
from harnessy.tools.code import code_tools
from harnessy.tools.sandbox import run_command

SYSTEM = (
    "You fix bugs in a small Python project in your workspace. Read the code and the tests, find the "
    "bug, fix it with edit_file, and run the tests with run_tests until they pass. Never change the "
    "tests. Finish with one sentence saying what was wrong."
)


# --- Week 8 exercise -------------------------------------------------------------------


def make_agent(model: Model, workspace: str | Path) -> Agent:
    """The code agent. Configuration only:

    - tools = code_tools(workspace)
    - a StopCheck whose check runs the tests (run_command([sys.executable, "-m", "pytest", "-q",
      "-p", "no:cacheprovider"], workspace, timeout_s=120, max_output=1_000_000)) and returns None
      if they pass, else a message telling the model the tests still fail, with the last 1,500
      characters of the output. The agent can't say "done" until the tests pass (week 6).
    - Agent(model, tools, system=SYSTEM, hooks=[that StopCheck], max_steps=20)
    """

    def tests_pass(result: Any) -> str | None:
        run = run_command(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], Path(workspace), timeout_s=120, max_output=1_000_000
        )
        if run.exit_code == 0:
            return None
        return "The tests still fail. Run run_tests, fix the code (not the tests), and try again.\n" + run.output[-1500:]

    return Agent(model, tools=code_tools(workspace), system=SYSTEM, hooks=[StopCheck(tests_pass)], max_steps=20)
