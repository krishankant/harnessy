# Beginner's Guide to Claude Tool Use

Tool use (also known as function calling) allows Claude to connect to external systems, databases, APIs, and web utilities. Instead of relying solely on its static training data, Claude can fetch real-time information, perform calculations, run code, and trigger actions in the real world.

This guide breaks down how tool use works, how tools are structured, how Anthropic processes tool calls, and the step-by-step sequence of events, complete with visual flowcharts and sequence diagrams.

---

## 1. What is a Tool? (The Smart Chef Analogy)

To understand tool use, imagine **Claude as a Master Chef** working in a restaurant kitchen:

- **Without Tools**: Claude knows thousands of recipes by heart (its training data). However, if a customer asks for a recipe using today's market price for fresh salmon, Claude can only estimate based on historical knowledge.
- **With Tools**: You equip Claude's kitchen with specialized appliances and live digital scales (Tools). 
  - Claude **does not press the buttons itself**—it writes down exact instructions: *"Place salmon on scale #2 and set unit to grams."*
  - **Your application (the Assistant)** takes the instruction, runs the scale, and hands the weight back to Claude.
  - Claude reads the result and tells the customer: *"The fresh salmon weighs 450 grams and costs $18.50 today."*

### The Tool-Use Contract
Tool use is a **formal agreement** between your application and Claude:
1. **You define** what tools exist, what they do, and what parameters they require.
2. **Claude decides** when to use a tool based on the user's question.
3. **Your application executes** the actual tool code (for client tools) and sends the output back to Claude.

> **Key Rule**: Claude *never* executes your client-side code directly. Claude only outputs structured JSON requesting a tool call, and your application fulfills that request.

---

## 2. Where Tools Run: Client vs. Server Tools

Not all tools run in the same place. Tools fall into three distinct categories based on where the code executes:

```
                      ┌─────────────────────────────────────────┐
                      │            TOOL CATEGORIES              │
                      └────────────────────┬────────────────────┘
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         │                                                                   │
┌────────┴────────┐                                                 ┌────────┴────────┐
│  CLIENT TOOLS   │                                                 │  SERVER TOOLS   │
│ (You Execute)   │                                                 │(Anthropic Runs) │
└────────┬────────┘                                                 └────────┬────────┘
         │                                                                   │
 ┌───────┴──────────────────────┐                                   ┌────────┴────────┐
 │                              │                                   │ - web_search    │
┌┴───────────────┐     ┌────────┴────────┐                          │ - web_fetch     │
│ User-Defined   │     │ Anthropic Schema│                          │ - code_execution│
│ (Your Custom   │     │ (Pre-Trained    │                          │ - tool_search   │
│  APIs & DBs)   │     │  Bash, Browser) │                          └─────────────────┘
└────────────────┘     └─────────────────┘
```

| Category | Execution Environment | Examples | Who Writes Schema? | Who Executes Code? |
| :--- | :--- | :--- | :--- | :--- |
| **User-Defined Client Tools** | Your Application | `get_weather`, `create_calendar_event`, SQL queries | You | Your Application |
| **Anthropic-Schema Client Tools** | Your Application | `bash`, `text_editor`, `memory`, `computer`, `browser` | Anthropic (Pre-trained) | Your Application |
| **Server-Executed Tools** | Anthropic Infrastructure | `web_search`, `web_fetch`, `code_execution`, `tool_search` | Anthropic | Anthropic Servers |

---

## 3. High-Level Architecture & Flowchart

The interaction between the User, your Application, the Claude API, and External Services follows a structured round-trip loop.

### Visual Flowchart: The Tool-Use Lifecycle

```
 ┌──────────┐            ┌─────────────────┐            ┌────────────┐            ┌──────────────────┐
 │   User   │            │ Your App/Agent  │            │ Claude API │            │ External Service │
 └────┬─────┘            └────────┬────────┘            └─────┬──────┘            └────────┬─────────┘
      │                           │                           │                            │
      │ 1. "What's the weather    │                           │                            │
      │    in San Francisco?"     │                           │                            │
      ├──────────────────────────►│                           │                            │
      │                           │ 2. POST /messages         │                            │
      │                           │    (User prompt + Tools)  │                            │
      │                           ├──────────────────────────►│                            │
      │                           │                           │ 3. Evaluates prompt        │
      │                           │                           │    against tool schemas    │
      │                           │                           │                            │
      │                           │ 4. Response:              │                            │
      │                           │    stop_reason: "tool_use"│                            │
      │                           │    tool_use: get_weather  │                            │
      │                           │◄──────────────────────────┤                            │
      │                           │                           │                            │
      │                           │ 5. Runs get_weather()     │                            │
      │                           ├───────────────────────────────────────────────────────►│
      │                           │ 6. Weather data returned  │                            │
      │                           │◄───────────────────────────────────────────────────────┤
      │                           │                           │                            │
      │                           │ 7. POST /messages         │                            │
      │                           │    (History + tool_result)│                            │
      │                           ├──────────────────────────►│                            │
      │                           │                           │ 8. Synthesizes final       │
      │                           │                           │    natural language reply  │
      │                           │ 9. Response:              │                            │
      │                           │    stop_reason: "end_turn"│                            │
      │                           │◄──────────────────────────┤                            │
      │ 10. "The weather in SF is │                           │                            │
      │     15°C and cloudy."     │                           │                            │
      │◄──────────────────────────┤                           │                            │
```

---

## 4. Anatomy of a Tool Definition

To give Claude a tool, you define three main parameters inside the `tools` array of your API request:

```json
{
  "name": "get_weather",
  "description": "Retrieves current weather conditions for a specified city and state. Returns temperature in requested units.",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "The city and state, e.g. San Francisco, CA"
      },
      "unit": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
        "description": "Unit of measurement"
      }
    },
    "required": ["location"]
  }
}
```

### Key Components Explained
1. **`name`**: A unique identifier matching `^[a-zA-Z0-9_-]{1,128}$` (e.g. `get_weather`).
2. **`description`**: A detailed explanation of what the tool does, when to use it, and what data it returns. **This is the single most important factor in tool accuracy.**
3. **`input_schema`**: A standard JSON Schema object defining required and optional arguments, data types, and allowed values.

### Good vs. Poor Descriptions

> ❌ **Poor Description**: `"Gets the stock price for a ticker."`  
> *Problem*: Leaves Claude guessing about market regions, currency, limitations, and formatting.

> ✅ **Good Description**: `"Retrieves the current stock price for a given ticker symbol. The ticker symbol must be a valid symbol for a publicly traded company on a major US stock exchange like NYSE or NASDAQ. Returns the latest trade price in USD. Use this when asked for real-time market prices."`  
> *Benefit*: Explains exact scope, region, currency, and trigger conditions.

---

## 5. The Step-by-Step Sequence of Events

Let's walk through a concrete step-by-step scenario where a user asks:  
*"Schedule a 30-minute meeting with Alice and Bob on Monday at 10am."*

### Step 1: Client Sends Request
Your application sends the user prompt along with the tool schema to the Messages API:

```python
response = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=1024,
    tools=my_tools,
    messages=[{"role": "user", "content": "Schedule a 30-min meeting with Alice and Bob..."}]
)
```

### Step 2: System Prompt Injection & Decision
Behind the scenes, the Claude API automatically constructs a special system prompt incorporating your tool definitions:

```
In this environment you have access to a set of tools you can use to answer the user's question.
Here are the functions available in JSONSchema format:
[ { "name": "create_calendar_event", ... } ]
```

Claude reads the prompt, decides that `create_calendar_event` is required, and stops text generation.

### Step 3: API Responds with `stop_reason: "tool_use"`
The API returns a response containing a `tool_use` content block:

```json
{
  "id": "msg_01Aq9w938a90dw8q",
  "stop_reason": "tool_use",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll help schedule that meeting for you."
    },
    {
      "type": "tool_use",
      "id": "toolu_01A09q90qw90lq917835lq9",
      "name": "create_calendar_event",
      "input": {
        "title": "Sync with Alice and Bob",
        "start": "2026-03-30T10:00:00",
        "end": "2026-03-30T10:30:00",
        "attendees": ["alice@example.com", "bob@example.com"]
      }
    }
  ]
}
```

### Step 4: Your App Executes the Function
Your code extracts the function name (`create_calendar_event`) and arguments from `input`, calls your local Google/Outlook Calendar API, and receives a result: `{"event_id": "evt_998", "status": "confirmed"}`.

### Step 5: Sending `tool_result` Back
Your app appends the assistant's turn and sends a new user message containing a `tool_result` block.

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
      "content": "{\"event_id\": \"evt_998\", \"status\": \"confirmed\"}"
    }
  ]
}
```

> **Strict Formatting Rules**:
> 1. `tool_result` blocks **must immediately follow** the assistant's `tool_use` message.
> 2. `tool_use_id` **must match** the `id` provided by Claude.
> 3. `tool_result` blocks **must come first** in the `content` array before any user text.

### Step 6: Final Natural Language Answer
Claude processes the tool result and returns its final answer with `stop_reason: "end_turn"`:

```
"I've scheduled your 30-minute meeting with Alice and Bob for Monday, March 30 at 10:00 AM."
```

---

## 6. The Agentic Loop & Advanced Patterns

### The Agentic While Loop
Real-world tasks often require **multiple consecutive tool calls** (e.g., checking calendar availability *first*, then creating the event). You handle this with an **agentic loop**:

```python
# Keep conversation history in a list
messages = [{"role": "user", "content": user_prompt}]

response = client.messages.create(model="claude-opus-5-5", tools=tools, messages=messages)

# Loop while Claude requests tools
while response.stop_reason == "tool_use":
    # 1. Process all tool calls in response.content
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = run_local_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result)
            })
    
    # 2. Append assistant response and user tool_results to history
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})
    
    # 3. Request next turn from Claude
    response = client.messages.create(model="claude-opus-5-5", tools=tools, messages=messages)

# Loop ends when stop_reason is "end_turn"
print(response.content[0].text)
```

### Parallel Tool Execution
Claude can request multiple tools in a single response (e.g., fetching weather for San Francisco *and* New York simultaneously). Your code should iterate over all `tool_use` blocks, execute them, and return all `tool_result` blocks together in one user message.

### Error Handling with `is_error`
If your tool execution encounters a failure (e.g. database timeout or invalid parameter), do not crash your program! Return the error to Claude with `"is_error": true`:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
  "content": "Error: Max attendees exceeded (limit 10). Please reduce invite list.",
  "is_error": true
}
```

When Claude sees `is_error: true`, it reads the error message and gracefully retries, asks the user for clarification, or offers an alternative solution.

### Simplifying with Tool Runner SDK
Writing manual while loops can be tedious. The Anthropic SDK provides a built-in **Tool Runner** that automates the loop, schema generation, and error handling:

```python
from anthropic import beta_tool

@beta_tool
def get_weather(location: str) -> str:
    """Get current weather for a location."""
    return "15°C, Partly Cloudy"

# Tool Runner automatically manages the agentic loop until completion
final_message = client.beta.messages.tool_runner(
    model="claude-opus-5-5",
    tools=[get_weather],
    messages=[{"role": "user", "content": "What's the weather in SF?"}]
).until_done()

print(final_message.content[0].text)
```

---

## 7. Controlling Tool Usage (`tool_choice`)

You can control whether Claude is allowed or forced to use tools using the `tool_choice` parameter:

```
                          ┌───────────────────────────┐
                          │    tool_choice Options    │
                          └─────────────┬─────────────┘
                                        │
      ┌──────────────────┬──────────────┴──────────────┬──────────────────┐
      │                  │                             │                  │
┌─────┴──────┐    ┌──────┴─────┐                ┌──────┴─────┐    ┌──────┴─────┐
│  {"auto"}  │    │  {"any"}   │                │ {"tool"}   │    │  {"none"}  │
└─────┬──────┘    └──────┬─────┘                └──────┬─────┘    └─────┬──────┘
      │                  │                             │                  │
Default: Claude   Forces Claude                 Forces a          Prevents all
decides whether   to call AT LEAST              SPECIFIC named    tool use.
to call a tool.   ONE tool.                     tool.             Generates prose.
```

- **`{"type": "auto"}`** *(Default)*: Claude dynamically decides whether to call a tool or reply directly in plain text.
- **`{"type": "auto"}` / `{"type": "any"}` / `{"type": "tool"}`**: Control tool forcing options where supported.
- **`{"type": "none"}`**: Disables tool calls entirely.

---

## 8. Summary Cheat Sheet

| Event / Field | Meaning | Standard Value / Format |
| :--- | :--- | :--- |
| **`stop_reason`** | Indicates why Claude paused | `"tool_use"` (needs tool execution) or `"end_turn"` (finished) |
| **`tool_use` Block** | Request from Claude to run a tool | Contains `id`, `name`, and `input` dictionary |
| **`tool_result` Block** | Response from application to Claude | Contains `tool_use_id`, `content`, and optional `is_error` |
| **Matching ID** | Connects call request to call result | `tool_result.tool_use_id == tool_use.id` |
| **Message Ordering** | Strict requirement in conversation history | `user` (`tool_result`) MUST immediately follow `assistant` (`tool_use`) |

---

**Next:** [`function-calling-vs-mcp.md`](function-calling-vs-mcp.md) moves a tool out of your app and into an MCP server. It shows that the `tool_use`/`tool_result` exchange above doesn't change, and what MCP adds around it.
