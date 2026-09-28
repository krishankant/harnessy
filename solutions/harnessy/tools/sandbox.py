"""A sandbox for commands (week 7): a subprocess in the workspace, with a scrubbed environment,
a time limit that really kills, and capped output. POSIX only (macOS, Linux).

Not a security boundary on its own: the command still runs as you. Docker is the stretch."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from harnessy.tools.registry import truncate
from harnessy.tools.schema import tool
from harnessy.types import Tool

SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TERM")


@dataclass(frozen=True)
class CommandResult:
    exit_code: int | None  # None if it was killed for taking too long
    output: str  # stdout and stderr together
    timed_out: bool


# --- Week 7 exercise -------------------------------------------------------------------


def run_command(
    command: list[str] | str,
    workdir: str | Path,
    timeout_s: float = 30.0,
    max_output: int = 10_000,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run command in workdir and return what happened. Never raises for a failing command.

    - A list runs directly; a str runs through /bin/sh (shell=isinstance(command, str)).
    - Environment: ONLY the SAFE_ENV_KEYS that exist in os.environ, plus HOME=str(workdir),
      plus env. Your API keys must not reach the command.
    - stdout and stderr merged (stderr=subprocess.STDOUT), text mode (errors="replace"),
      stdin=subprocess.DEVNULL, start_new_session=True (the command gets its own process group).
    - proc.communicate(timeout=timeout_s). On subprocess.TimeoutExpired: os.killpg(proc.pid,
      signal.SIGKILL) kills the whole group (children too), then communicate() again to collect
      what was printed, and return exit_code None, timed_out True.
    - Output goes through truncate(output, max_output) (week 3).
    """
    full_env = {k: os.environ[k] for k in SAFE_ENV_KEYS if k in os.environ}
    full_env["HOME"] = str(workdir)
    full_env.update(env or {})
    proc = subprocess.Popen(
        command,
        cwd=workdir,
        env=full_env,
        shell=isinstance(command, str),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout_s)
        return CommandResult(proc.returncode, truncate(output, max_output), False)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        return CommandResult(None, truncate(output or "", max_output), True)


# --- Given -----------------------------------------------------------------------------


def shell_tool(root: str | Path, timeout_s: float = 30.0) -> Tool:
    """A run_shell tool confined to root. Tagged with all three trifecta legs: a shell can read
    your files, read untrusted output, and reach the network."""

    @tool(timeout_s=timeout_s + 5, tags={"private_data", "untrusted_input", "external_send"})
    def run_shell(command: str) -> str:
        """Run a shell command in the workspace folder and return its exit code and output. Only PATH and a few locale variables are passed in.

        Args:
            command: The command line, run with /bin/sh.
        """
        result = run_command(command, Path(root), timeout_s)
        if result.timed_out:
            return f"timed out after {timeout_s:g}s; the process was killed\n{result.output}"
        return f"exit code {result.exit_code}\n{result.output}"

    return run_shell
