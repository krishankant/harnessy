"""Week 5: run the eval suite against real models.

Run from the repo root:
    uv run python -m scripts.evals --tasks easy --trials 1          # cheap first run
    uv run python -m scripts.evals --provider both --trials 3       # the week 5 "done when"
Results go to evals/results/ (git-ignored); each run is compared with the previous one.
"""

from dotenv import load_dotenv

load_dotenv()

import argparse  # noqa: E402
import datetime  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402

from harnessy.evals.runner import aggregate, compare, format_table, run_evals  # noqa: E402
from harnessy.evals.tasks import load_tasks  # noqa: E402
from harnessy.models.anthropic import AnthropicModel  # noqa: E402
from harnessy.models.openai import OpenAIModel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
RESULTS = ROOT / "evals" / "results"
PROVIDERS = {"anthropic": AnthropicModel, "openai": OpenAIModel}


def previous(provider: str, before: str) -> dict | None:
    files = sorted(p for p in RESULTS.glob(f"*-{provider}.json") if p.name < before)
    return json.loads(files[-1].read_text()) if files else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["anthropic", "openai", "both"], default="both")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--tasks", help="a difficulty (easy/medium/hard) or an id prefix")
    parser.add_argument("--judge", choices=["anthropic", "openai", "none"], default="anthropic")
    args = parser.parse_args()
    try:
        tasks = load_tasks(TASKS, args.tasks)
        if not tasks:
            print(f"no tasks match {args.tasks!r}")
            return 1
        judge = None if args.judge == "none" else PROVIDERS[args.judge]()
    except NotImplementedError as e:
        print(f"Finish the exercises first ({e})")
        return 1
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    names = list(PROVIDERS) if args.provider == "both" else [args.provider]
    for name in names:
        try:
            model = PROVIDERS[name]()
        except Exception as e:
            print(f"\n{name} failed to start: {type(e).__name__}: {e}")
            continue
        print(f"\n== {model.name}: {len(tasks)} tasks x {args.trials} trials")

        def show(r) -> None:
            status = "PASS" if r.passed else "FAIL"
            print(f"  {status} {r.task_id} #{r.trial} steps={r.steps} stop={r.stop_reason}" + (f" error={r.error}" if r.error else ""))

        try:
            records = run_evals(tasks, lambda: model, args.trials, judge, RESULTS / "traces" / f"{stamp}-{name}", show)
        except NotImplementedError as e:
            print(f"Finish the exercises first ({e})")
            return 1
        summary = aggregate(records)
        print(format_table(summary))
        RESULTS.mkdir(parents=True, exist_ok=True)
        out = RESULTS / f"{stamp}-{name}.json"
        out.write_text(json.dumps({"provider": name, "model": model.name, "timestamp": stamp, "summary": summary,
                                   "records": [asdict(r) for r in records]}, indent=2))
        before = previous(name, out.name)
        if before:
            changes = compare(before["summary"], summary)
            print(f"\nchanges since {before['timestamp']}:" if changes else f"\nno change since {before['timestamp']}")
            for line in changes:
                print("  " + line)
        print(f"saved {out.relative_to(ROOT)}; traces in {(RESULTS / 'traces' / f'{stamp}-{name}').relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
