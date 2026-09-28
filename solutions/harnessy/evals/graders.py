"""Graders (week 5): check the end result, not the path the agent took. Code checks first; a
model judge only where code can't decide."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harnessy.models.base import Model
from harnessy.tools.files import resolve_inside
from harnessy.types import Message

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
    text = f"Rubric:\n{criteria}\n\nWork to grade:\n{answer}"
    reply = judge.complete([Message("user", text=text)], [], system=JUDGE_PROMPT).message.text.strip()
    words = reply.split(maxsplit=1)
    first = words[0].strip(".,:;!*").upper() if words else ""
    rest = words[1].strip() if len(words) > 1 else ""
    if first in ("PASS", "FAIL"):
        return CheckResult(first == "PASS", f"judge: {first} {rest}".strip())
    return CheckResult(False, f"judge reply unclear: {reply[:100]!r}")


def grade(check: dict[str, Any], answer: str, workspace: str | Path, judge: Model | None = None) -> CheckResult:
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
    A missing key -> CheckResult(False, "<type> check is missing '<key>'"); any other exception
    -> CheckResult(False, "<type> check failed: <ExceptionType>: <message>").
    """
    kind = check.get("type")
    try:
        if kind == "file_exists":
            ok = resolve_inside(workspace, check["path"]).is_file()
            return CheckResult(ok, f"{check['path']} {'exists' if ok else 'does not exist'}")
        if kind in ("file_contains", "file_lacks"):
            target = resolve_inside(workspace, check["path"])
            if not target.is_file():
                return CheckResult(False, f"{check['path']} does not exist")
            found = check["text"] in target.read_text()
            ok = found if kind == "file_contains" else not found
            return CheckResult(ok, f"{check['path']} {'contains' if found else 'does not contain'} {check['text']!r}")
        if kind == "answer_contains":
            ok = check["text"].lower() in answer.lower()
            return CheckResult(ok, f"answer {'contains' if ok else 'does not contain'} {check['text']!r}")
        if kind == "answer_matches":
            ok = re.search(check["pattern"], answer, re.I) is not None
            return CheckResult(ok, f"answer {'matches' if ok else 'does not match'} /{check['pattern']}/")
        if kind == "json_valid":
            target = resolve_inside(workspace, check["path"])
            if not target.is_file():
                return CheckResult(False, f"{check['path']} does not exist")
            try:
                value = json.loads(target.read_text())
            except json.JSONDecodeError as e:
                return CheckResult(False, f"{check['path']} is not valid JSON: {e}")
            if "equals" in check and value != check["equals"]:
                return CheckResult(False, f"{check['path']} is valid JSON but not the expected value: {json.dumps(value)[:200]}")
            return CheckResult(True, f"{check['path']} is valid JSON" + (" with the expected value" if "equals" in check else ""))
        if kind == "rubric":
            if judge is None:
                return CheckResult(False, "rubric check needs a judge model")
            subject = resolve_inside(workspace, check["path"]).read_text() if "path" in check else answer
            return judge_verdict(judge, check["criteria"], subject)
        return CheckResult(False, f"unknown check type: {kind!r}")
    except KeyError as e:
        return CheckResult(False, f"{kind} check is missing {e}")
    except Exception as e:
        return CheckResult(False, f"{kind} check failed: {type(e).__name__}: {e}")
