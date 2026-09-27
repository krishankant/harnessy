# harnessy

A small agent harness you build yourself, one week at a time. It works with any model provider: Anthropic, OpenAI, or a local model through Ollama. It follows the 8-week *Harness Engineering* learning plan. Each week you read a short lesson, fill in the missing pieces of the code, and make the tests pass.

This repo currently covers **week 1** (a provider-neutral model interface) and **week 2** (the agent loop).

## Setup

```bash
uv sync                  # installs anthropic, openai, python-dotenv and pytest
cp .env.example .env     # then fill in your keys and model names
```

`.env` is read by `load_dotenv()` at the top of the two scripts in `scripts/`. **The tests need no keys and make no network calls.** If you use `ant auth login` for Anthropic, leave `ANTHROPIC_API_KEY` commented out, because an empty value would override your login.

## How each week works

1. Read `lessons/weekN-*.md`.
2. Run that week's tests and watch them fail: `uv run pytest tests/weekN`.
3. Fill in the functions that raise `NotImplementedError` until the tests pass.
4. Run the week's live script to see it work against real models.
5. Write your answers to the lesson's questions in `NOTES.md`.

## What's given and what you write

| File | Week | Status |
| --- | --- | --- |
| `harnessy/types.py` | 1 | Given: the provider-neutral types |
| `harnessy/models/base.py` | 1 | Given: the `Model` protocol |
| `harnessy/models/anthropic.py` | 1 | **Exercise:** 4 translation functions (`AnthropicModel.complete` is given) |
| `harnessy/models/openai.py` | 1 | **Exercise:** 4 translation functions (`OpenAIModel.complete` is given) |
| `harnessy/models/scripted.py` | 2 | Given: a fake model for tests |
| `harnessy/loop.py` | 2 | **Exercise:** `Agent.run` and `Agent._run_tool` |
| `scripts/week1_compare.py` | 1 | Given: the same question on both providers |
| `scripts/week2_demo.py` | 2 | Given: the loop answering a two-tool question |

## Checking against the reference solutions

`solutions/harnessy/` is a complete copy of the package. The same tests and scripts run against it when you set `HARNESSY_IMPL=solutions`:

```bash
HARNESSY_IMPL=solutions uv run pytest
HARNESSY_IMPL=solutions uv run python -m scripts.week2_demo
```

This is handled in `tests/conftest.py` and `scripts/__init__.py`. Look at the solutions after your own version passes.

## Layout

```
harnessy/            your copy: the exercises live here
solutions/harnessy/  reference copy, complete
lessons/             one lesson per week
tests/week1, week2/  offline tests (fixtures in tests/fixtures/)
scripts/             live demos (need .env)
docs/superpowers/    the design spec and implementation plan for this repo
```
