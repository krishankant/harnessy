# Beginner's Guide to OpenAI Tool Use

Tool use (OpenAI calls it **function calling**) lets an OpenAI model such as GPT-5.5 connect to external systems, databases, APIs and web utilities. Instead of relying only on its training data, the model can fetch live information, run calculations, call your code and trigger actions in the real world.

This guide explains how tool use works with OpenAI: how tools are defined, where they run, the step-by-step sequence of a tool call, and the agent loop that ties it together. It is the OpenAI companion to [`claude-tool-use-guide-v2.md`](claude-tool-use-guide-v2.md), and section 9 maps one onto the other.

**Two APIs.** OpenAI offers tool calling through two endpoints, and you will meet both:

- **Responses API** (`POST /v1/responses`): OpenAI's newer API, recommended for new projects. This guide uses it in the main walkthrough.
- **Chat Completions** (`POST /v1/chat/completions`): the older, widely copied format. harnessy's `OpenAIModel` uses it, because Ollama, vLLM, LM Studio and OpenRouter all speak it (section 10).

The idea is identical in both; only the JSON shapes differ, and this guide shows both where it matters.

---

## 1. What is a Tool? (The Smart Chef Analogy)

Imagine **the model as a Master Chef** in a restaurant kitchen:

- **Without tools**: the chef knows thousands of recipes by heart (its training data). Asked for a recipe priced at *today's* market rate for fresh salmon, it can only estimate.
- **With tools**: you equip the kitchen with appliances and a live digital scale (tools).
  - The chef **does not press the buttons itself**. It writes exact instructions on a ticket: *"Put the salmon on scale #2, unit: grams."*
  - **Your application** reads the ticket, runs the scale, and hands the weight back.
  - The chef reads the result and tells the customer: *"The salmon weighs 450 grams and costs $18.50 today."*

### The Function-Calling Contract

Tool use is a **formal agreement** between your application and the model:

1. **You define** which tools exist, what they do and what arguments they take (a JSON Schema).
2. **The model decides** when to call a tool, based on the conversation.
3. **Your application executes** the function (for your own tools) and sends the output back.

> **Key Rule**: the model *never* runs your code. It returns a structured request to call a function, with the arguments as a **JSON string**, and your application fulfils it.

---

## 2. Where Tools Run: Function Tools vs. Hosted Tools

Tools fall into three groups, depending on where the code runs:

```
                      ┌─────────────────────────────────────────┐
                      │            TOOL CATEGORIES              │
                      └────────────────────┬────────────────────┘
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         │                                                                   │
┌────────┴────────┐                                                 ┌────────┴────────┐
│ FUNCTION TOOLS  │                                                 │  HOSTED TOOLS   │
│ (You Execute)   │                                                 │ (OpenAI Runs)   │
└────────┬────────┘                                                 └────────┬────────┘
         │                                                                   │
 ┌───────┴──────────────────────┐                                ┌───────────┴─────────┐
 │                              │                                │ - web_search        │
┌┴───────────────┐     ┌────────┴─────────┐                      │ - file_search       │
│ Your custom    │     │ OpenAI-defined,  │                      │ - code_interpreter  │
│ functions      │     │ you run them     │                      │ - image_generation  │
│ (APIs, DBs)    │     │ (computer use)   │                      │ - remote MCP server │
└────────────────┘     └──────────────────┘                      └─────────────────────┘
```

| Category | Where it runs | Examples | Who writes the schema? | Who executes the code? |
| :--- | :--- | :--- | :--- | :--- |
| **Function tools** | Your application | `get_weather`, `create_calendar_event`, SQL queries | You | Your application |
| **OpenAI-defined tools you execute** | Your application (your machine, browser or VM) | computer use: the model asks for clicks and keystrokes, you perform them and return a screenshot | OpenAI | Your application |
| **Hosted (built-in) tools** | OpenAI's infrastructure | `web_search`, `file_search`, `code_interpreter`, `image_generation`, remote MCP servers | OpenAI | OpenAI |

Hosted tools exist in the **Responses API**; Chat Completions has almost none. You enable one by listing it, e.g. `"tools": [{"type": "web_search"}]`, and its activity shows up as its own output items. The rest of this guide is about **function tools**, the ones you run.

---

## 3. High-Level Architecture & Flowchart

The user, your application, the OpenAI API and your external services take part in a round trip:

```
 ┌──────────┐            ┌─────────────────┐            ┌────────────┐            ┌──────────────────┐
 │   User   │            │ Your App/Agent  │            │ OpenAI API │            │ External Service │
 └────┬─────┘            └────────┬────────┘            └─────┬──────┘            └────────┬─────────┘
      │                           │                           │                            │
      │ 1. "What's the weather    │                           │                            │
      │    in San Francisco?"     │                           │                            │
      ├──────────────────────────►│                           │                            │
      │                           │ 2. POST /v1/responses     │                            │
      │                           │    (input + tools)        │                            │
      │                           ├──────────────────────────►│                            │
      │                           │                           │ 3. Model weighs the prompt │
      │                           │                           │    against tool schemas    │
      │                           │                           │                            │
      │                           │ 4. Response: output has a │                            │
      │                           │    function_call item     │                            │
      │                           │    (name, call_id, args)  │                            │
      │                           │◄──────────────────────────┤                            │
      │                           │                           │                            │
      │                           │ 5. Runs get_weather()     │                            │
      │                           ├───────────────────────────────────────────────────────►│
      │                           │ 6. Weather data returned  │                            │
      │                           │◄───────────────────────────────────────────────────────┤
      │                           │                           │                            │
      │                           │ 7. POST /v1/responses     │                            │
      │                           │    (function_call_output  │                            │
      │                           │     with the same call_id)│                            │
      │                           ├──────────────────────────►│                            │
      │                           │                           │ 8. Writes the final        │
      │                           │                           │    natural-language reply  │
      │                           │ 9. Response: output has a │                            │
      │                           │    message, no calls      │                            │
      │                           │◄──────────────────────────┤                            │
      │ 10. "It's 15°C and cloudy │                           │                            │
      │     in San Francisco."    │                           │                            │
      │◄──────────────────────────┤                           │                            │
```

The same round trip in Chat Completions: step 4 is `finish_reason: "tool_calls"` with entries in `message.tool_calls`; step 7 sends one `{"role": "tool"}` message per call; step 9 is `finish_reason: "stop"`.

---

## 4. Anatomy of a Tool Definition

You give the model a tool by putting a definition in the `tools` array of your request.

**Responses API** (flat):

```json
{
  "type": "function",
  "name": "get_weather",
  "description": "Retrieves current weather conditions for a city. Returns the temperature in the requested unit. Use this whenever the user asks about current weather.",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "The city and state, e.g. San Francisco, CA"
      },
      "unit": {
        "type": ["string", "null"],
        "enum": ["celsius", "fahrenheit", null],
        "description": "Unit of measurement; null means celsius"
      }
    },
    "required": ["location", "unit"],
    "additionalProperties": false
  },
  "strict": true
}
```

**Chat Completions** wraps the same fields in a `function` object:

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "...",
    "parameters": { "...": "the same JSON Schema" },
    "strict": true
  }
}
```

### Key Components Explained

1. **`type: "function"`**: marks this as a function tool you execute (hosted tools use other types, like `"web_search"`).
2. **`name`**: a unique identifier such as `get_weather` (letters, digits, `_` and `-`; keep it short and descriptive).
3. **`description`**: what the tool does, when to use it and what it returns. **This is the biggest single factor in how well the model uses the tool.**
4. **`parameters`**: a JSON Schema for the arguments: types, required fields, allowed values.
5. **`strict`**: with `true`, OpenAI guarantees the arguments match your schema (structured outputs). Strict mode has two rules: `additionalProperties: false`, and **every** property listed in `required`. An optional field becomes nullable instead, like `unit` above (`"type": ["string", "null"]`).

### Good vs. Poor Descriptions

> ❌ **Poor description**: `"Gets the stock price for a ticker."`
> *Problem*: leaves the model guessing about exchanges, currency, freshness and when to call it.

> ✅ **Good description**: `"Retrieves the current stock price for a ticker symbol listed on a major US exchange (NYSE or NASDAQ). Returns the latest trade price in USD. Use this when the user asks for a live market price; do not use it for historical prices."`
> *Benefit*: states scope, currency, output and the trigger condition.

---

## 5. The Step-by-Step Sequence of Events

A user asks:
*"Schedule a 30-minute meeting with Alice and Bob on Monday at 10am."*

### Step 1: Your App Sends the Request

```python
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY

response = client.responses.create(
    model="gpt-5.5",
    instructions="You are a scheduling assistant.",
    tools=my_tools,
    input=[{"role": "user", "content": "Schedule a 30-min meeting with Alice and Bob on Monday at 10am."}],
)
```

### Step 2: The Model Decides

OpenAI gives the model your tool definitions alongside the conversation. The model sees that `create_calendar_event` fits the request and, instead of only writing text, emits a function call.

### Step 3: The Response Contains a `function_call` Item

In the Responses API, `output` is a **list of items**, and a tool call is an item of its own:

```json
{
  "id": "resp_67ccd2bed1ec8190",
  "object": "response",
  "status": "completed",
  "output": [
    { "type": "reasoning", "id": "rs_67ccd2bf", "summary": [] },
    {
      "type": "function_call",
      "id": "fc_12345xyz",
      "call_id": "call_9Xq2lP0w",
      "name": "create_calendar_event",
      "arguments": "{\"title\":\"Sync with Alice and Bob\",\"start\":\"2026-10-12T10:00:00\",\"end\":\"2026-10-12T10:30:00\",\"attendees\":[\"alice@example.com\",\"bob@example.com\"]}"
    }
  ],
  "usage": { "input_tokens": 312, "output_tokens": 61, "total_tokens": 373 }
}
```

Two things to notice:

- **`arguments` is a JSON string**, not an object. Parse it with `json.loads` (and handle bad JSON if you don't use strict mode).
- **There are two ids.** `call_id` (`call_…`) is the one you send back with the result. The item's own `id` (`fc_…`) is a different identifier; don't use it for matching.

### Step 4: Your App Executes the Function

Your code reads `name` and the parsed `arguments`, calls your calendar API, and gets a result: `{"event_id": "evt_998", "status": "confirmed"}`.

### Step 5: Send the Result Back as `function_call_output`

```json
{
  "type": "function_call_output",
  "call_id": "call_9Xq2lP0w",
  "output": "{\"event_id\": \"evt_998\", \"status\": \"confirmed\"}"
}
```

There are two ways to send it:

- **Let OpenAI keep the history**: pass `previous_response_id="resp_67ccd2bed1ec8190"` and only the new `function_call_output` item.
- **Keep the history yourself (stateless)**: send the whole conversation in `input`: the user message, the `reasoning` item, the `function_call` item, then the `function_call_output`. Use this with `store=False`, or whenever your own code needs to see every turn (as an agent harness does).

> **Matching Rules**:
> 1. Every `function_call` needs **exactly one** `function_call_output`, with the **same `call_id`**. A missing output is an error.
> 2. Keep the `function_call` item in the history before its output, and send **reasoning items back** with it (reasoning models use them to continue their train of thought).
> 3. `output` is usually a string. A function that returns an image or a file can send a list of image or file objects instead.
> 4. In Chat Completions the result is a message instead: `{"role": "tool", "tool_call_id": "call_9Xq2lP0w", "content": "..."}`, **one per call**, directly after the assistant message that made the calls.

### Step 6: The Final Answer

The model reads the result and replies with a normal message. There is no `function_call` in `output` this time, so the turn is over; the SDK's `response.output_text` joins its text:

```
"I've scheduled your 30-minute meeting with Alice and Bob for Monday, October 12 at 10:00 AM."
```

---

## 6. The Agent Loop & Advanced Patterns

### The Agent Loop (Responses API)

Real tasks often need **several tool calls in a row** (check availability first, then create the event). You handle that with a loop that keeps going while the model asks for tools:

```python
import json
from openai import OpenAI

client = OpenAI()
history = [{"role": "user", "content": user_prompt}]

response = client.responses.create(model="gpt-5.5", tools=tools, input=history)

while True:
    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        break  # no tool requested: this is the final answer

    # 1. Keep everything the model produced (reasoning + function_call items)
    history += response.output

    # 2. Run every requested tool and add one output per call
    for call in calls:
        try:
            result = run_local_tool(call.name, json.loads(call.arguments))
            output = json.dumps(result)
        except Exception as e:  # a failure is a result, not a crash (see below)
            output = f"Error: {e}"
        history.append({"type": "function_call_output", "call_id": call.call_id, "output": output})

    # 3. Ask the model for its next step
    response = client.responses.create(model="gpt-5.5", tools=tools, input=history)

print(response.output_text)
```

### The Same Loop in Chat Completions

This is the loop harnessy's `Agent.run` performs through its OpenAI adapter:

```python
messages = [{"role": "user", "content": user_prompt}]

while True:
    resp = client.chat.completions.create(model="gpt-5.5", tools=tools, messages=messages)
    msg = resp.choices[0].message
    if resp.choices[0].finish_reason != "tool_calls":
        break
    messages.append(msg)  # the assistant message with its tool_calls
    for call in msg.tool_calls:
        result = run_local_tool(call.function.name, json.loads(call.function.arguments))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

print(msg.content)
```

In a real agent, also cap the number of steps, tokens and time so the loop always ends; harnessy's loop (week 2) does exactly that.

### Parallel Tool Calls

The model may ask for several functions in one response (weather for San Francisco **and** New York). Run them all and send back one output per `call_id`. To force one call at a time, set `parallel_tool_calls=False`.

### Errors: There Is No `is_error` Flag

Claude's `tool_result` has `is_error: true`. **OpenAI has no error flag.** Put the error in the output text itself, plainly enough for the model to act on:

```json
{
  "type": "function_call_output",
  "call_id": "call_9Xq2lP0w",
  "output": "ERROR: Max attendees exceeded (limit 10). Ask the user to shorten the invite list."
}
```

The model reads it and retries with different arguments, asks the user, or offers another way. (harnessy's adapter prefixes failed results with `ERROR:` for the same reason.)

### Simplifying with the Agents SDK

Writing the loop by hand is good for learning. For production, OpenAI's **Agents SDK** (`pip install openai-agents`) runs it for you: it builds schemas from Python functions, executes calls and loops until the agent finishes:

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return "15°C, partly cloudy"

agent = Agent(name="Assistant", instructions="Answer briefly.", model="gpt-5.5", tools=[get_weather])
result = Runner.run_sync(agent, "What's the weather in SF?")
print(result.final_output)
```

---

## 7. Controlling Tool Usage (`tool_choice`)

```
                          ┌───────────────────────────┐
                          │    tool_choice options    │
                          └─────────────┬─────────────┘
                                        │
      ┌──────────────────┬──────────────┴──────────────┬──────────────────┐
      │                  │                             │                  │
┌─────┴──────┐    ┌──────┴──────┐              ┌───────┴──────┐    ┌──────┴─────┐
│  "auto"    │    │ "required"  │              │ a function   │    │   "none"   │
└─────┬──────┘    └──────┬──────┘              └───────┬──────┘    └──────┬─────┘
      │                  │                             │                  │
Default: the       Must call AT              Must call THIS          No tool calls;
model decides.     LEAST ONE tool.           named function.         plain text only.
```

| You want | Responses API | Chat Completions |
| :--- | :--- | :--- |
| Model decides (default) | `"auto"` | `"auto"` |
| Must call some tool | `"required"` | `"required"` |
| Must call this tool | `{"type": "function", "name": "get_weather"}` | `{"type": "function", "function": {"name": "get_weather"}}` |
| Only some of the tools, without dropping the rest from the request | `{"type": "allowed_tools", "mode": "auto", "tools": [...]}` | the same shape |
| No tools | `"none"` | `"none"` |

`"mode": "required"` inside `allowed_tools` makes the model call one of the listed tools.

---

## 8. Summary Cheat Sheet

| Event / Field | Responses API | Chat Completions |
| :--- | :--- | :--- |
| **Tool definition** | `{type: "function", name, description, parameters, strict}` | `{type: "function", function: {name, description, parameters, strict}}` |
| **The model wants a tool** | `output` contains a `function_call` item | `finish_reason: "tool_calls"` and `message.tool_calls` |
| **The call** | `name`, `arguments` (JSON **string**), `call_id` | `function.name`, `function.arguments` (JSON **string**), `id` |
| **Your result** | `{type: "function_call_output", call_id, output}` | `{role: "tool", tool_call_id, content}`, one per call |
| **Matching id** | `function_call_output.call_id == function_call.call_id` | `tool_call_id == tool_calls[].id` |
| **Finished** | no `function_call` in `output`; text in `output_text` | `finish_reason: "stop"` |
| **Errors** | no flag: say `ERROR: ...` in `output` | no flag: say it in `content` |
| **System prompt** | `instructions` | a `system` (or `developer`) message |
| **History** | send it all, or chain with `previous_response_id` | always send it all |

---

## 9. Claude ↔ OpenAI at a Glance

The same concepts, side by side with the [Claude guide](claude-tool-use-guide-v2.md):

| Concept | Claude (Messages API) | OpenAI Responses | OpenAI Chat Completions |
| :--- | :--- | :--- | :--- |
| Schema field | `input_schema` | `parameters` | `function.parameters` |
| Model asks for a tool | `stop_reason: "tool_use"` + `tool_use` block | `function_call` item | `finish_reason: "tool_calls"` |
| Arguments | `input`: a JSON **object** | `arguments`: a JSON **string** | `arguments`: a JSON **string** |
| Call id → result id | `id` → `tool_use_id` | `call_id` → `call_id` | `id` → `tool_call_id` |
| Where results go | `tool_result` blocks in **one user message** | `function_call_output` items | one `tool` message **per call** |
| Error flag | `is_error: true` | none | none |
| Done | `stop_reason: "end_turn"` | no `function_call` in `output` | `finish_reason: "stop"` |
| Force a tool | `{"type": "any"}` / `{"type": "tool", "name": ...}` | `"required"` / `{"type": "function", "name": ...}` | `"required"` / `{"type": "function", "function": {...}}` |
| Server-run tools | web search, web fetch, code execution | web search, file search, code interpreter, image generation, remote MCP | almost none |
| Loop helper | Tool Runner (`client.beta.messages.tool_runner`) | Agents SDK (`Runner.run`) | Agents SDK |

For every difference in depth (reasoning items, streaming, caching, usage fields), read [`model-interfaces.md`](model-interfaces.md).

---

## 10. How harnessy Does It

harnessy keeps one provider-neutral loop and puts every OpenAI detail in an adapter, `harnessy/models/openai.py` (week 1):

- **`to_openai_tools`** wraps each `ToolSpec` as `{"type": "function", "function": {...}}`.
- **`to_openai_messages`** turns harnessy messages into Chat Completions messages: assistant tool calls go into `tool_calls`, each `ToolResult` becomes its own `{"role": "tool"}` message, and failed results get the `ERROR:` prefix.
- **`from_openai_response`** parses `arguments` defensively (bad JSON becomes `{"_raw": ...}`, which the registry rejects with a message the model can read) and maps `finish_reason` onto harnessy's stop reasons.
- **`OpenAIModel`** accepts `base_url`, so the same adapter talks to Ollama, vLLM, LM Studio or OpenRouter (`OPENAI_BASE_URL`).

Why Chat Completions and not Responses, and what a Responses adapter would change: [`model-interfaces.md` section 10](model-interfaces.md#10-why-harnessy-uses-chat-completions).

---

## Sources

- OpenAI: [Function calling](https://developers.openai.com/api/docs/guides/function-calling), [Migrating to Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses), [Agents SDK](https://openai.github.io/openai-agents-python/)
- In this repo: [`model-interfaces.md`](model-interfaces.md), `harnessy/models/openai.py`
