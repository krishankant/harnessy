"""MCP (week 9): talk to Model Context Protocol servers over stdio, and turn their tools into
ordinary harnessy Tools.

Targets MCP 2026-07-28 ("modern": no session, every request carries its protocol version in
_meta) and falls back to the initialize handshake of 2025-11-25 and earlier ("legacy") for
servers that don't speak it yet."""

from __future__ import annotations

import itertools
import json
import os
import queue
import re
import subprocess
import threading
from typing import Any, Callable, Iterable

from harnessy.types import Tool, ToolSpec

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
UNSUPPORTED_PROTOCOL_VERSION = -32022
CLIENT_INFO = {"name": "harnessy", "version": "0.9"}
ALL_TAGS = frozenset({"private_data", "untrusted_input", "external_send"})
ENV_KEYS = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR")
META = "io.modelcontextprotocol/"


class McpError(Exception):
    """A JSON-RPC error from the server, or a protocol situation this client can't handle."""

    def __init__(self, code: int | None, message: str, data: Any = None):
        super().__init__(f"MCP error {code}: {message}" if code is not None else f"MCP error: {message}")
        self.code, self.message, self.data = code, message, data


class McpTimeout(McpError):
    def __init__(self, message: str):
        super().__init__(None, message)


class McpToolError(Exception):
    """An MCP tool ran and reported a failure (isError: true)."""


# --- Given: the stdio transport ----------------------------------------------------------


class StdioTransport:
    """Runs an MCP server as a subprocess; one JSON-RPC message per line on stdin and stdout.

    The server gets a minimal environment (ENV_KEYS plus `env`): your API keys don't reach a
    third-party server unless you pass them on purpose. Its stderr (logs) is discarded."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None, cwd: str | None = None):
        full_env = {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
        full_env.update(env or {})
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=full_env, cwd=cwd
        )
        self._pending: dict[Any, queue.Queue] = {}
        self._lock = threading.Lock()
        self._closed = False
        self.notifications: list[dict[str, Any]] = []
        threading.Thread(target=self._read, daemon=True).start()

    def expect(self, request_id: Any) -> queue.Queue:
        """Register interest in the response to request_id (before sending the request)."""
        box: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            if self._closed:
                box.put(None)
            else:
                self._pending[request_id] = box
        return box

    def forget(self, request_id: Any) -> None:
        with self._lock:
            self._pending.pop(request_id, None)

    def send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":")) + "\n"  # json.dumps never emits a raw newline
        try:
            with self._lock:
                self.proc.stdin.write(line.encode())
                self.proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError) as e:
            raise ConnectionError("the MCP server is not running") from e

    def _read(self) -> None:
        for raw in self.proc.stdout:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue  # not a message; the spec forbids it, so skip it
            if isinstance(message, dict) and "id" in message and ("result" in message or "error" in message):
                with self._lock:
                    box = self._pending.pop(message["id"], None)
                if box is not None:
                    box.put(message)
            else:
                self.notifications = (self.notifications + [message])[-100:]
        with self._lock:  # the server closed stdout: wake everyone still waiting
            self._closed = True
            boxes, self._pending = list(self._pending.values()), {}
        for box in boxes:
            box.put(None)

    def close(self, timeout_s: float = 2.0) -> None:
        """Close stdin, wait; then terminate, wait; then kill (the spec's shutdown order)."""
        if self.proc.poll() is not None:
            return
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        for step in (lambda: None, self.proc.terminate, self.proc.kill):
            step()
            try:
                self.proc.wait(timeout=timeout_s)
                return
            except subprocess.TimeoutExpired:
                continue


# --- The client ---------------------------------------------------------------------------


class McpClient:
    def __init__(self, transport: StdioTransport, timeout_s: float = 30.0, probe_timeout_s: float = 3.0):
        self.transport = transport
        self.timeout_s = timeout_s
        self.probe_timeout_s = probe_timeout_s
        self.era: str | None = None  # "modern" or "legacy" once connected
        self.protocol_version: str | None = None
        self.server_info: dict[str, Any] = {}
        self.instructions = ""
        self._ids = itertools.count(1)

    # --- Given ---

    @classmethod
    def stdio(cls, command: list[str], env: dict[str, str] | None = None, cwd: str | None = None, **options: Any) -> McpClient:
        return cls(StdioTransport(command, env, cwd), **options)

    def __enter__(self) -> McpClient:
        try:
            self.connect()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.transport.close()

    def _roundtrip(self, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Send one request and wait for its response (the raw JSON-RPC message)."""
        box = self.transport.expect(message["id"])
        self.transport.send(message)
        try:
            response = box.get(timeout=timeout)
        except queue.Empty:
            self.transport.forget(message["id"])
            raise McpTimeout(f"no answer to {message['method']} within {timeout:g}s") from None
        if response is None:
            raise ConnectionError("the MCP server closed the connection")
        return response

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.transport.send(message)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    # --- Week 9 exercise ---

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return its result.

        - The message is {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}.
        - If self.era == "modern", params["_meta"] gets the per-request protocol fields:
          f"{META}protocolVersion": self.protocol_version, f"{META}clientInfo": CLIENT_INFO,
          f"{META}clientCapabilities": {} (keep any _meta the caller passed).
        - Wait with self._roundtrip(message, timeout or self.timeout_s) (given).
        - An "error" response -> raise McpError(error["code"], error["message"], error.get("data")).
        - The result's "resultType" defaults to "complete". Anything else (e.g. "input_required",
          where the server wants user input mid-request) -> raise McpError(None, ...) naming the
          resultType and saying this client can't answer input requests.
        - Return the result dict.
        """
        raise NotImplementedError("Week 9 exercise: McpClient.request")

    def connect(self) -> None:
        """Find out which era the server speaks, then get ready to use it.

        1. Assume modern (self.era = "modern", self.protocol_version = MODERN_VERSION) and send
           "server/discover" with timeout=self.probe_timeout_s.
        2. It answers: modern. MODERN_VERSION must be in result["supportedVersions"] (else raise
           McpError naming them). Store self.server_info = result["_meta"][f"{META}serverInfo"]
           (default {}) and self.instructions = result.get("instructions", "").
        3. McpError with code UNSUPPORTED_PROTOCOL_VERSION: the server is modern but doesn't
           speak our version. Do NOT fall back: raise McpError naming error.data["supported"].
        4. Any other McpError, or McpTimeout: the server is legacy -> self._initialize_legacy().
        (A ConnectionError means the server isn't running: let it propagate.)
        """
        raise NotImplementedError("Week 9 exercise: McpClient.connect")

    def _initialize_legacy(self) -> None:
        """The legacy handshake (2025-11-25 and earlier).

        Set self.era = "legacy" (so request() stops adding _meta), then request "initialize"
        with {"protocolVersion": LEGACY_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO}.
        The server's result["protocolVersion"] must be in LEGACY_VERSIONS (else McpError naming
        it); store it in self.protocol_version, plus server_info (result["serverInfo"]) and
        instructions. Finally send the "notifications/initialized" notification (self.notify).
        """
        raise NotImplementedError("Week 9 exercise: McpClient._initialize_legacy")

    def list_tools(self) -> list[dict[str, Any]]:
        """Every tool the server offers: request "tools/list" (with {"cursor": c} after the
        first page), add result["tools"], and follow result["nextCursor"] until there is none.
        A server that pages forever is a bug: after 100 pages raise McpError mentioning
        "100 pages"."""
        raise NotImplementedError("Week 9 exercise: McpClient.list_tools")


# --- Week 9 exercise ------------------------------------------------------------------------


def content_to_text(result: dict[str, Any]) -> str:
    """Turn a tools/call result into text for the model. One line per content item:
    text -> its text; image/audio -> "[image: <mimeType>]" / "[audio: <mimeType>]";
    resource_link -> "[resource: <uri>]"; resource (embedded) -> its "text" if it has one,
    else "[resource: <uri>]"; anything else -> "[<type> content]". Join with "\\n".
    If there is no content at all but there is "structuredContent", return json.dumps of it.
    Nothing at all -> ""."""
    raise NotImplementedError("Week 9 exercise: content_to_text")


# --- Given ----------------------------------------------------------------------------------


def tool_name(name: str, prefix: str | None = None) -> str:
    """A tool name every provider accepts: only [A-Za-z0-9_-], prefixed "prefix__name" to keep
    two servers' tools apart, at most 64 characters."""
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    if prefix:
        clean = f"{re.sub(r'[^A-Za-z0-9_-]', '_', prefix)}__{clean}"
    return clean[:64]


def _caller(client: McpClient, name: str) -> Callable[..., str]:
    def call(**arguments: Any) -> str:
        result = client.call_tool(name, arguments)
        text = content_to_text(result)
        if result.get("isError"):
            raise McpToolError(text or "the tool reported an error")
        return text

    return call


# --- Week 9 exercise ------------------------------------------------------------------------


def mcp_tools(
    client: McpClient, prefix: str | None = None, tags: Iterable[str] = ALL_TAGS, timeout_s: float | None = None
) -> list[Tool]:
    """One harnessy Tool per MCP tool (client.list_tools()), in the server's order:

    - name: tool_name(mcp["name"], prefix)
    - description: mcp["description"], else mcp["title"], else mcp["name"]
    - parameters: a copy of mcp["inputSchema"] (default {}) with "type" defaulting to "object"
      and "properties" to {} (the registry validates against it, like any other tool)
    - fn: _caller(client, mcp["name"]) (given: calls the tool, joins the content, and raises
      McpToolError when the result has isError, so the model gets an error result)
    - timeout_s as given, max_chars None, tags=frozenset(tags). The default is all three
      lethal-trifecta legs: an MCP server, and the annotations it gives its tools, are
      untrusted unless you say otherwise.
    """
    raise NotImplementedError("Week 9 exercise: mcp_tools")
