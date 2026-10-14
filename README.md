# harnessy

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#setup)
[![Providers](https://img.shields.io/badge/providers-Anthropic%20%7C%20OpenAI%20%7C%20Ollama-6f42c1.svg)](docs/model-interfaces.md)
[![Protocol](https://img.shields.io/badge/MCP-2026--07--28%20%2B%20legacy-008080.svg)](lessons/week9-mcp.md)
[![Tests](https://img.shields.io/badge/tests-offline%20pytest%20suite-2ea44f.svg)](#cli--commands-cheat-sheet)

**[8-Week Learning Plan](LEARNING_PLAN.md)** · **[What is a Harness?](docs/what-is-a-harness.md)** · **[System Architecture](docs/architecture.md)** · **[Failure Gallery](docs/failures.md)** · **[Documentation Hub](docs/README.md)**

---

**harnessy** is a minimal, production-minded Python agent harness you build yourself, one week at a time. It works across **Anthropic**, **OpenAI**, and local models via **Ollama** without external agent frameworks (no LangChain, LangGraph, or CrewAI—only the official provider SDKs and the Python standard library).

Each week you read a focused engineering lesson, implement the missing pieces in `harnessy/`, wire them into your agent loop, and verify your implementation against an offline `pytest` suite and live demos. Complete reference implementations live side-by-side in `solutions/harnessy/`.

> **What is a harness?** A language model only turns text into text. The **harness** is the runtime around it: the loop that keeps calling the model, the tools it can execute, the context window manager that shapes what it sees, the memory store that persists across runs, the hooks and approval policies that enforce safety in code, and the trace/eval harness that measures whether changes actually improve outcomes.

---

## Table of Contents

1. [Quick Start: What You Build](#quick-start-what-you-build)
2. [System Architecture](#system-architecture)
3. [The Idea in One Picture (The Body Metaphor)](#the-idea-in-one-picture)
4. [The 9-Week Curriculum](#the-weeks)
5. [Deep-Dive Engineering Guides](#guides)
6. [Setup & Installation](#setup)
7. [How Each Week Works](#how-each-week-works)
8. [CLI & Commands Cheat Sheet](#cli--commands-cheat-sheet)
9. [What's Given and What You Write](#whats-given-and-what-you-write)
10. [Repository Layout](#layout)

---

## Quick Start: What You Build

By Week 7, your entire agent harness fits into a clean, composable API where **an agent is just configuration** (a model, a system prompt, tools, hooks, and limits):

```python
from pathlib import Path
from harnessy.approvals import ApprovalHook, terminal_approver
from harnessy.context import ContextManager, Summarize
from harnessy.loop import Agent
from harnessy.models.anthropic import AnthropicModel
from harnessy.models.retry import RetryingModel
from harnessy.todo import TodoList
from harnessy.tools.files import file_tools
from harnessy.tools.schema import tool
from harnessy.tracer import Tracer


@tool
def add(a: int, b: int) -> int:
    """Add two integers together.

    Args:
        a: First integer
        b: Second integer
    """
    return a + b


model = RetryingModel(AnthropicModel())
todo = TodoList()
workspace = Path("./workspace")

agent = Agent(
    model=model,
    system="You are a careful assistant. Plan with todo before editing files.",
    tools=[add, todo.tool(), *file_tools(workspace)],
    context=ContextManager(budget_tokens=16_000, strategy=Summarize(model)),
    hooks=[
        todo,
        ApprovalHook({"write_file": "ask"}, approver=terminal_approver),
    ],
    tracer=Tracer(Path("trace.jsonl")),
    max_steps=15,
    max_tokens_total=50_000,
    timeout_s=60.0,
    max_cost_usd=0.25,
)

result = agent.run("Calculate 17 + 25 and write the result to answer.txt.")
print(f"Stop: {result.stop_reason} | Steps: {len(result.steps)} | Cost: ${result.cost_usd:.4f}")
print(result.final_text)
```

---

## System Architecture

One loop sits in the middle (`Agent.run`). Everything else plugs in at one of **five extension points**: the **Model** protocol, the **ToolRegistry**, the **ContextManager**, **HookRunner** lifecycle points, and hard **Limits** (`steps`, `tokens`, `time`, `cost`, and build-time `check_trifecta`).

```mermaid
flowchart TB
  subgraph EVAL["Evaluation & Capstone (Weeks 5 & 8)"]
    TASKS["YAML Tasks<br/>evals/tasks · evals/capstone"]
    TRIAL["run_trial · isolated workspace"]
    GRADE["Graders: code checks · LLM rubric · citations"]
    AGENTS["Capstone Agents (Config Only)<br/>research · code · data"]
    TASKS --> TRIAL
    TRIAL --> AGENTS
    TRIAL --> GRADE
  end

  subgraph CORE["Core Harness Loop (Week 2)"]
    RUN["Agent.run(task)<br/>Limits: max_steps · max_tokens · timeout_s · max_cost_usd"]
    STREAM["Agent.stream(task) (Week 7)<br/>TextDelta · ToolStart · ToolEnd · Done"]
  end

  CTX["ContextManager (Week 4)<br/>Append-only history → budgeted view<br/>DropOldest · Summarize · clear_old_results"]
  HOOKS["HookRunner (Week 6)<br/>on_start · before/after_model<br/>before/after_tool · on_stop · on_finish"]
  REG["ToolRegistry (Week 3)<br/>JSON Schema validation · daemon timeout · output truncation"]
  SAFE["check_trifecta (Week 7)<br/>Build-time lethal-trifecta enforcement"]
  COST["Cost Meter (Week 7)<br/>price_for · cost_usd"]

  subgraph HOOKLIST["Pluggable Hooks"]
    AH["ApprovalHook (allow / ask / deny)"]
    TD["TodoList (tool + before_model hook)"]
    SC["StopCheck (reject premature end_turn)"]
    TH["TraceHook → JSONL Tracer"]
  end

  subgraph TOOLS["Tools (@tool & MCP)"]
    F["File Tools: read_file · write_file · edit_file"]
    W["Web Tools: web_search · http_get"]
    MEM["MemoryStore: remember · recall"]
    SH["Sandboxed Shell: run_shell · run_tests"]
    D["Read-Only SQLite: list_tables · run_sql · plot_query"]
    SUB["Subagents: spawn_subagent (fresh context)"]
    MCPT["MCP Tools (Week 9): McpClient over stdio"]
  end

  subgraph MODELS["Provider-Neutral Model Layer (Week 1 & 7)"]
    RETRY["RetryingModel (exponential backoff + full jitter)"]
    ANT["AnthropicModel (Messages API)"]
    OAI["OpenAIModel (Chat Completions + Ollama)"]
    SCR["ScriptedModel (deterministic offline tests)"]
  end

  AGENTS --> RUN
  STREAM --> RUN
  RUN --> CTX
  RUN --> HOOKS
  RUN --> REG
  RUN -.-> SAFE
  RUN -.-> COST
  HOOKS --> HOOKLIST
  REG --> TOOLS
  SUB -. "spawns child Agent" .-> RUN
  RUN -- "complete(view, specs, system)" --> RETRY
  RETRY --> ANT
  RETRY --> OAI
  RUN --> SCR

  classDef safety fill:#fbf0e1,stroke:#a65b00,color:#1b2230
  classDef core fill:#e8f0fe,stroke:#4a6fd8,color:#1b2230
  class SAFE,AH,SH safety
  class RUN,STREAM core
```

### Runtime Execution Flow (`Agent.run`)

```mermaid
sequenceDiagram
  autonumber
  participant U as Caller
  participant A as Agent.run
  participant H as HookRunner
  participant C as ContextManager
  participant M as Model
  participant R as ToolRegistry

  U->>A: run(task)
  A->>H: on_start(agent, task)
  loop Every Step
    A->>A: Check limits (max_steps, max_tokens, timeout_s, max_cost_usd)
    A->>C: prepare(messages)
    C-->>A: budgeted view
    A->>H: before_model(view)
    H-->>A: view (or Block -> finish("blocked"))
    A->>M: complete(view, specs, system)
    M-->>A: ModelResponse
    A->>H: after_model(response)
    alt Model requests tool_calls (clean stop)
      loop Each ToolCall in order
        A->>H: before_tool(call)
        alt Allowed
          A->>R: call(call) (validate -> run with timeout -> truncate)
          R-->>A: ToolResult
        else Blocked by Hook
          H-->>A: ToolResult(is_error=True, reason)
        end
        A->>H: after_tool(call, result)
      end
      Note over A: Append ONE user Message containing all ToolResults
    else Model stops without tool calls (end_turn)
      A->>H: on_stop(result)
      alt Rejected (e.g. StopCheck fails)
        H-->>A: Rejection reason appended as user Message (continue loop)
      else Accepted
        A->>H: on_finish(result)
        A-->>U: RunResult
      end
    end
  end
```

For all 17 architectural, sequence, class, and state diagrams, see **[`docs/architecture.md`](docs/architecture.md)** or open the interactive viewer **[`docs/architecture-archify.html`](docs/architecture-archify.html)** in a browser.

---

## The Idea in One Picture

The model is the brain; the harness is the body. Each week builds one organ: the loop is the heartbeat, tools are the hands, evals are the check-up, and the trifecta check is the immune system. [`docs/anatomy.html`](docs/anatomy.html) explains every organ with a second everyday analogy and where the metaphor breaks (open it in a browser).

![The model is the brain, the harness is the body: each harnessy layer mapped to a body part](docs/anatomy.png)

![Every organ card: what the body part does, what the harness layer does, a second everyday analogy, and what breaks without it](docs/anatomy-organs.png)

---

## The Weeks

**Start here:** [`LEARNING_PLAN.md`](LEARNING_PLAN.md) is the complete 8-week learning plan (plus Bonus Week 9): what each week is about, curated readings, what to build, and how you know you're done. Each week has a self-contained hands-on tutorial in [`lessons/`](lessons/):

| Week | You Build | Lesson | Tests | Live Demo |
| :---: | --- | --- | --- | --- |
| **1** | **One interface for every model provider** (`Message`, `ToolCall`, `ModelResponse`, `AnthropicModel`, `OpenAIModel`) | [`week1-model-interface.md`](lessons/week1-model-interface.md) | `tests/week1` (42) | `uv run python -m scripts.week1_compare` |
| **2** | **The agent loop** (`Agent.run`, `Agent._run_tool`, step/token/time limits, `ScriptedModel`) | [`week2-agent-loop.md`](lessons/week2-agent-loop.md) | `tests/week2` (18) | `uv run python -m scripts.week2_demo` |
| **3** | **Tools** (`@tool` schema reflection, `ToolRegistry` validation/timeouts/truncation, confined `file_tools`) | [`week3-tools.md`](lessons/week3-tools.md) | `tests/week3` (39) | `uv run python -m scripts.week3_demo` |
| **4** | **Context and memory** (`ContextManager`, `DropOldest`, `Summarize`, `clear_old_results`, `MemoryStore`) | [`week4-context-and-memory.md`](lessons/week4-context-and-memory.md) | `tests/week4` (34) | `uv run python -m scripts.week4_demo` |
| **5** | **Traces and evals** (`Tracer` JSONL, `format_timeline`, 15 YAML tasks, code & judge graders, `evals` runner) | [`week5-traces-and-evals.md`](lessons/week5-traces-and-evals.md) | `tests/week5` (45) | `uv run python -m scripts.week5_demo` |
| **6** | **Control flow** (`HookRunner`, `ApprovalHook`, `spawn_subagent`, `TodoList`, `StopCheck`, `TraceHook`) | [`week6-control-flow.md`](lessons/week6-control-flow.md) | `tests/week6` (34) | `uv run python -m scripts.week6_demo` |
| **7** | **Production concerns** (`RetryingModel`, `stream_agent`, `cost_usd`, process-group sandbox, `check_trifecta`) | [`week7-production.md`](lessons/week7-production.md) | `tests/week7` (44) | `uv run python -m scripts.week7_demo` |
| **8** | **Capstone: prove it's generic** (Research, Code, and Data agents on an unchanged `Agent` + 15 capstone evals) | [`week8-capstone.md`](lessons/week8-capstone.md) | `tests/week8` (32) | `uv run python -m scripts.week8_demo` |
| **9** *(bonus)* | **Tools from any MCP server** (`McpClient` over stdio, modern + legacy discovery, `mcp_tools` bridge) | [`week9-mcp.md`](lessons/week9-mcp.md) | `tests/week9` (23) | `uv run python -m scripts.week9_demo` |

---

## Guides

The [`docs/`](docs/README.md) directory contains 18 in-depth engineering guides that pair with the weekly lessons.

### 1. Core Foundations & Architecture
| If you want to know… | Read |
| --- | --- |
| What a harness is, with the whole loop on one screen and each line marked by its week | [`docs/what-is-a-harness.md`](docs/what-is-a-harness.md) *(read this first)* |
| Why each part exists: eight ways an agent goes wrong, run with and without the fix | [`docs/failures.md`](docs/failures.md) (`uv run python -m scripts.failure_gallery`) |
| How all the parts fit together (17 architecture, sequence, state, and class diagrams) | [`docs/architecture.md`](docs/architecture.md) · interactive [`architecture-archify.html`](docs/architecture-archify.html) |
| Which Claude Code feature matches each harnessy module, side by side | [`docs/claude-code.md`](docs/claude-code.md) |

### 2. Model APIs, Tool Use & MCP (Weeks 1, 3, 9)
| If you want to know… | Read |
| --- | --- |
| How the Anthropic and OpenAI APIs differ (messages, tool calls, stop reasons, usage, streaming) | [`docs/model-interfaces.md`](docs/model-interfaces.md) |
| How tool use works with Claude from the ground up, with visual flowcharts and decision trees | [`docs/claude-tool-use-guide-v2.md`](docs/claude-tool-use-guide-v2.md) · [`AI_Tool_Use_Execution_Loop.png`](docs/AI_Tool_Use_Execution_Loop.png) |
| How OpenAI function calling works (Responses API & Chat Completions), mapped onto Claude's | [`docs/openai-tool-use-guide.md`](docs/openai-tool-use-guide.md) |
| How function calling and MCP differ, with one tool built both ways and the exact JSON payloads | [`docs/function-calling-vs-mcp.md`](docs/function-calling-vs-mcp.md) *(pairs with Week 9)* |
| How MCP messages travel under the hood: stdio pipes, JSON-RPC 2.0, and real captured traffic | [`docs/mcp-under-the-hood.md`](docs/mcp-under-the-hood.md) *(read after the one above)* |

### 3. Context, Memory & Observability (Weeks 4 & 5)
| If you want to know… | Read |
| --- | --- |
| The four kinds of agent memory (working, episodic, semantic, procedural) and how production systems build them | [`docs/memory.md`](docs/memory.md) · interactive [`memory-infographic.html`](docs/memory-infographic.html) |
| What an agent run looks like on disk: three real JSONL traces read line by line | [`docs/traces.md`](docs/traces.md) |
| How Claude Code stores a session as JSONL under `~/.claude` and how to inspect it with `jq` and Python | [`docs/claude-code-traces.md`](docs/claude-code-traces.md) |

### 4. Control Flow, Hooks, Planning & Subagents (Week 6)
| If you want to know… | Read |
| --- | --- |
| How to change the loop without editing it, with six tested hooks you can drop into any agent | [`docs/hooks.md`](docs/hooks.md) |
| The same hooks in Claude Code: events, settings, exit codes, JSON decisions, and the six examples ported | [`docs/claude-code-hooks.md`](docs/claude-code-hooks.md) |
| Hooks on the OpenAI side: Codex hooks vs. the Agents SDK's lifecycle hooks and guardrails | [`docs/openai-hooks.md`](docs/openai-hooks.md) |
| How an agent decides to launch a subagent, which levers control delegation, and six multi-agent patterns | [`docs/subagents.md`](docs/subagents.md) |
| How the model plans with `TodoList`, with traces from two real runs | [`docs/todo.md`](docs/todo.md) |
| What a skill is (on-demand instructions), and how harnessy loads one as a 25-line tool | [`docs/skills.md`](docs/skills.md) |

### 5. Security, Sandboxing & Production Engineering (Week 7)
| If you want to know… | Read |
| --- | --- |
| The lethal trifecta: how an injected web page steals private data, and how `check_trifecta` and taint tracking stop it | [`docs/trifecta.md`](docs/trifecta.md) |
| What `run_command` protects you from, what it does *not*, and how to add OS sandboxing (`sandbox-exec`, `bwrap`, Docker) | [`docs/sandbox.md`](docs/sandbox.md) (`uv run python -m scripts.sandbox_demo`) |

---

## Setup

```bash
uv sync                  # installs anthropic, openai, python-dotenv, pyyaml, and pytest
cp .env.example .env     # then fill in your keys and model names
```

`.env` is loaded by `load_dotenv()` at the top of each script in `scripts/`. **The unit test suite (`uv run pytest`) requires no API keys and makes zero network calls.** If you use `ant auth login` for Anthropic, leave `ANTHROPIC_API_KEY` commented out in `.env`, because an empty value overrides your login profile.

---

## How Each Week Works

```mermaid
flowchart LR
  R["1. Read<br/>lessons/weekN-*.md"] --> T["2. Run Tests<br/>uv run pytest tests/weekN"]
  T --> B["3. Implement & Wire<br/>Fill in harnessy/ & loop.py"]
  B --> P["4. Verify Green<br/>All tests pass"]
  P --> D["5. Run Live Demo<br/>uv run python -m scripts.weekN_demo"]
  D --> N["6. Reflect<br/>Answer prompts in NOTES.md"]
  style R fill:#e8f0fe,stroke:#4a6fd8,color:#1b2230
  style P fill:#eef8ee,stroke:#3a9a4a,color:#1b2230
```

1. **Read** `lessons/weekN-*.md`.
2. **Run that week's tests** and watch them fail: `uv run pytest tests/weekN`.
3. **Fill in the functions** that raise `NotImplementedError` until the tests pass. From Week 3 on, this step ends with a short *wire it in* exercise in your own `harnessy/loop.py`; the lesson gives the exact lines.
4. **Run the week's live script** to see it work against real models.
5. **Write your answers** to the lesson's reflection questions in `NOTES.md`.

---

## CLI & Commands Cheat Sheet

| Goal | Command |
| --- | --- |
| Run a single week's offline tests | `uv run pytest tests/week1` |
| Run all offline tests against your code | `uv run pytest` |
| Run all offline tests against the reference solutions | `HARNESSY_IMPL=solutions uv run pytest` |
| Run a live demo script (uses `.env`) | `uv run python -m scripts.week2_demo` |
| Run a live demo with the reference solutions | `HARNESSY_IMPL=solutions uv run python -m scripts.week7_demo` |
| Run core evals (5 easy tasks, 1 trial, Anthropic) | `uv run python -m scripts.evals --tasks easy --trials 1 --provider anthropic` |
| Run full Week 5 eval benchmark across both providers | `uv run python -m scripts.evals --provider both --trials 3` |
| Run Week 8 capstone suite (Research, Code, Data agents) | `uv run python -m scripts.evals --suite capstone --provider both --trials 3` |
| Inspect a saved JSONL trace as a readable timeline | `uv run python -m scripts.trace_view evals/results/traces/<run>/<task>-1.jsonl` |
| Run the 8-scenario Failure Gallery (without vs. with fix) | `uv run python -m scripts.failure_gallery` |
| Run the Sandbox security boundary demonstration | `uv run python -m scripts.sandbox_demo` |

---

## What's Given and What You Write

| File | Week | Status |
| --- | :---: | --- |
| `harnessy/types.py` | 1 | **Given:** provider-neutral dataclasses (`Message`, `ToolCall`, `ToolResult`, `ModelResponse`, `Usage`, `Tool`) |
| `harnessy/models/base.py` | 1 | **Given:** the `Model` protocol (`complete` and optional `stream`) |
| `harnessy/models/anthropic.py` | 1 | **Exercise:** 4 translation functions (`AnthropicModel.complete` is given) |
| `harnessy/models/openai.py` | 1 | **Exercise:** 4 translation functions (`OpenAIModel.complete` is given) |
| `scripts/week1_compare.py` | 1 | **Given:** sends the same multi-turn tool conversation to both providers |
| `harnessy/models/scripted.py` | 2 | **Given:** deterministic `ScriptedModel` for offline tests |
| `harnessy/loop.py` | 2–7 | **Exercise:** `Agent.run` and `Agent._run_tool`; Weeks 3–7 add incremental *wire it in* edits |
| `scripts/week2_demo.py` | 2 | **Given:** the loop answering a two-tool question |
| `harnessy/tools/schema.py` | 3 | **Exercise:** `json_type`, `schema_from_function` (`@tool` and `parse_docstring` are given) |
| `harnessy/tools/registry.py` | 3 | **Exercise:** `validate_args`, `truncate`, `ToolRegistry.call` |
| `harnessy/tools/files.py` | 3 | **Exercise:** `resolve_inside` (`file_tools` is given) |
| `harnessy/tools/web.py` | 3 | **Given:** `http_get` |
| `scripts/week3_demo.py` | 3 | **Given:** an agent writing and reading a file in a confined workspace |
| `harnessy/context.py` | 4 | **Exercise:** `estimate_tokens`, `clear_old_results`, `find_cut`, `Summarize.view`, `ContextManager.prepare` |
| `harnessy/memory.py` | 4 | **Exercise:** `MemoryStore.recall` (`memory_tools` is given) |
| `scripts/week4_demo.py` | 4 | **Given:** a long task with and without a `ContextManager`, then persistent memory across two runs |
| `harnessy/tracer.py` | 5 | **Exercise:** `Tracer.event`, `format_timeline` (`TraceHook` is given for Week 6) |
| `harnessy/evals/tasks.py` | 5 | **Exercise:** `load_task` (`load_tasks` is given) |
| `harnessy/evals/graders.py` | 5, 8 | **Exercise:** `grade`, `judge_verdict` (Week 5); `check_citations` (Week 8) |
| `harnessy/evals/runner.py` | 5 | **Exercise:** `aggregate`, `compare` (`run_trial`, `run_evals`, `format_table` are given) |
| `evals/tasks/*.yaml` | 5 | **Given:** 15 eval tasks (5 easy, 5 medium, 5 hard) |
| `scripts/trace_view.py` | 5 | **Given:** print a JSONL trace as a human-readable timeline |
| `scripts/evals.py` | 5 | **Given:** run eval suites, print and save results, compare with the previous run |
| `scripts/week5_demo.py` | 5 | **Given:** one traced run as a timeline, then 3 tasks scored before and after a change |
| `harnessy/hooks.py` | 6 | **Exercise:** `HookRunner` (`Hook`, `Block`, `StopCheck` are given) |
| `harnessy/approvals.py` | 6 | **Exercise:** `ApprovalHook.before_tool` (`terminal_approver` is given) |
| `harnessy/subagents.py` | 6 | **Exercise:** `subagent_tool` |
| `harnessy/todo.py` | 6 | **Exercise:** `TodoList.apply`, `render`, `before_model` |
| `scripts/week6_demo.py` | 6 | **Given:** an interactive approval prompt, then a two-subagent delegation task |
| `harnessy/models/retry.py` | 7 | **Exercise:** `is_retryable`, `backoff_delay`, `RetryingModel.complete` |
| `harnessy/models/openai_stream.py` | 7 | **Exercise:** `merge_openai_chunks` (each model's `stream()` is given) |
| `harnessy/streaming.py` | 7 | **Exercise:** `collect_stream`, `stream_agent` |
| `harnessy/cost.py` | 7 | **Exercise:** `price_for`, `cost_usd` (`PRICES` table is given, checked 2026-09-28) |
| `harnessy/tools/sandbox.py` | 7 | **Exercise:** `run_command` (`run_shell` is given) |
| `harnessy/safety.py` | 7 | **Exercise:** `check_trifecta` |
| `harnessy/tools/outbox.py` | 7 | **Given:** a fake `send_email` that records outgoing messages to a file |
| `scripts/week7_demo.py` | 7 | **Given:** streaming, a retried 429, a cost limit stop, and a blocked prompt injection |
| `harnessy/tools/localweb.py` | 8 | **Exercise:** `LocalWeb.search` (local HTTP server and `web_search` are given) |
| `harnessy/tools/code.py` | 8 | **Exercise:** `edit_text` (`code_tools` is given) |
| `harnessy/tools/data.py` | 8 | **Exercise:** `query_readonly` (`data_tools` and SVG chart generation are given) |
| `harnessy/agents/` | 8 | **Exercise:** `make_agent` for `research`, `code`, and `data` |
| `evals/corpus/` | 8 | **Given:** 16 HTML pages about the fictional Orwen region, served locally |
| `evals/capstone/` | 8 | **Given:** 15 capstone tasks, 5 per agent (`scripts.evals --suite capstone`) |
| `scripts/week8_demo.py` | 8 | **Given:** the research, code, and data agents solving one capstone task each, with traces |
| `harnessy/mcp.py` | 9 | **Exercise:** `McpClient.request`, `connect`, `_initialize_legacy`, `list_tools`, `content_to_text`, `mcp_tools` |
| `scripts/mcp_notes_server.py` | 9 | **Given:** a working MCP server (notes) supporting both modern and legacy MCP eras |
| `scripts/week9_demo.py` | 9 | **Given:** an agent using MCP tools; `--server` connects to any stdio MCP server |

---

## Checking Against the Reference Solutions

`solutions/harnessy/` is a complete reference copy of the package. The same tests and scripts run against it when you set `HARNESSY_IMPL=solutions`:

```bash
HARNESSY_IMPL=solutions uv run pytest
HARNESSY_IMPL=solutions uv run python -m scripts.week2_demo
```

This switch is handled in `tests/conftest.py` and `scripts/__init__.py`. Compare your solution with `diff harnessy/<file>.py solutions/harnessy/<file>.py` after your tests pass.

---

## Layout

```text
harnessy/            your copy: the exercises live here
solutions/harnessy/  reference copy, complete and passing all tests
lessons/             one hands-on tutorial per week (week1 through week9)
tests/week1…week9/   offline unit and wiring tests (fixtures in tests/fixtures/)
evals/
  ├── tasks/         week 5 core eval tasks (15 YAML files: easy, medium, hard)
  ├── capstone/      week 8 domain agent tasks (research, code, data)
  ├── corpus/        16 fictional HTML pages served by LocalWeb for offline research evals
  └── results/       saved benchmark JSONs and JSONL traces (git-ignored)
scripts/             live demos and CLI utilities (load .env)
docs/                18 engineering guides, Mermaid diagrams, and interactive HTML views
```
