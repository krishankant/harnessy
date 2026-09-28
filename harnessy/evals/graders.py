"""Graders (week 5): check the end result, not the path the agent took. Code checks first; a
model judge only where code can't decide."""

from __future__ import annotations

import json
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harnessy.models.base import Model
from harnessy.tools.files import resolve_inside
from harnessy.tools.sandbox import run_command
from harnessy.types import Message

if TYPE_CHECKING:
    from harnessy.tools.localweb import LocalWeb

JUDGE_PROMPT = (
    "You grade an AI agent's work against a rubric. Reply with PASS or FAIL as the first word, "
    "then one short sentence saying why."
)


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    detail: str


# --- Week 5 exercise -------------------------------------------------------------------


def judge_verdict(judge: Model, criteria: str, answer: str) -> CheckResult:
    """Ask the judge model once: judge.complete([Message("user", text=...)], [], system=JUDGE_PROMPT)
    with text "Rubric:\\n{criteria}\\n\\nWork to grade:\\n{answer}".

    The reply's first word, with punctuation and * stripped (strip(".,:;!*")) and upper-cased,
    decides: PASS -> CheckResult(True, "judge: PASS <rest>"), FAIL -> CheckResult(False,
    "judge: FAIL <rest>") (strip the result), anything else -> CheckResult(False,
    "judge reply unclear: <first 100 chars of the reply, repr>").
    """
    raise NotImplementedError("Week 5 exercise: judge_verdict")


def check_citations(answer: str, facts: list[str], web: LocalWeb) -> CheckResult:
    """Week 8: pass only if the answer's citations are real and support every fact.

    - URLs: re.findall(r"https?://\\S+", answer), each with trailing .,;:!?)]"'> stripped
      (Markdown links and <...> wrappers). None -> CheckResult(False, "the answer cites no URLs").
    - Every URL must be a page of web (web.slug_for(url) in web.pages), else
      CheckResult(False, "<url> is not a page on the local web").
    - Every fact must appear (case-insensitive) in the title or text of at least one cited page,
      else CheckResult(False, "no cited page supports: <missing facts joined '; '>").
    - Otherwise CheckResult(True, "<n> citation(s), all supported").
    """
    raise NotImplementedError("Week 8 exercise: check_citations")


def grade(
    check: dict[str, Any], answer: str, workspace: str | Path, judge: Model | None = None, web: LocalWeb | None = None
) -> CheckResult:
    """Grade one check. NEVER raises: every problem is a failed CheckResult with a readable detail.

    Paths always go through resolve_inside(workspace, path) (a check must not read outside).
    - file_exists {path}            -> "<path> exists" / "<path> does not exist"
    - file_contains {path, text}    -> case-sensitive; "<path> contains 'x'" / "does not contain 'x'";
                                       a missing file fails "<path> does not exist"
    - file_lacks {path, text}       -> passes if the file exists and does NOT contain text
    - answer_contains {text}        -> case-insensitive substring of answer
    - answer_matches {pattern}      -> re.search(pattern, answer, re.I)
    - json_valid {path, equals?}    -> parses; if "equals" is given the value must be equal;
                                       invalid JSON fails "<path> is not valid JSON: <error>"
    - rubric {criteria, path?}      -> no judge: CheckResult(False, "rubric check needs a judge model");
                                       otherwise judge_verdict on the file's text if path is given,
                                       else on the answer
    - citations {facts} (week 8)    -> no web: CheckResult(False, "citations check needs the local web");
                                       otherwise check_citations(answer, facts, web)
    - command_succeeds {command} (week 8) -> run it in the workspace with run_command (a leading
                                       "python" becomes sys.executable; timeout 180 s); passes on
                                       exit code 0, else says "exit code N" (or "timed out") and
                                       the last 300 characters of output
    A missing key -> CheckResult(False, "<type> check is missing '<key>'"); any other exception
    -> CheckResult(False, "<type> check failed: <ExceptionType>: <message>").
    """
    raise NotImplementedError("Week 5 exercise: grade")
