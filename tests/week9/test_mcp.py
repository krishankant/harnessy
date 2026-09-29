import sys
import time
from pathlib import Path

import pytest

from harnessy.approvals import ApprovalHook
from harnessy.loop import Agent
from harnessy.mcp import ALL_TAGS, McpClient, McpError, McpTimeout, content_to_text, mcp_tools, tool_name
from harnessy.models.scripted import ScriptedModel, text_reply, tool_reply
from harnessy.safety import TrifectaError
from harnessy.tools.registry import ToolRegistry
from harnessy.types import ToolCall

SERVER = [sys.executable, str(Path(__file__).with_name("fake_server.py"))]
ALL_NAMES = ["echo", "fail", "files.read", "mixed", "sleep", "ask", "env"]


def client(mode: str, **options) -> McpClient:
    return McpClient.stdio([*SERVER, mode], **options)


def test_a_modern_server():
    with client("modern") as c:
        assert (c.era, c.protocol_version) == ("modern", "2026-07-28")
        assert (c.server_info.get("name"), c.instructions) == ("fake", "Fake server.")
        assert content_to_text(c.call_tool("echo", {"text": "hi"})) == "hi (via 2026-07-28)"


def test_a_legacy_server_falls_back_to_initialize():
    with client("legacy") as c:
        assert (c.era, c.protocol_version, c.server_info.get("name")) == ("legacy", "2025-11-25", "fake-legacy")
        assert c.instructions == "Legacy fake."
        assert content_to_text(c.call_tool("echo", {"text": "hi"})) == "hi (via legacy)"


def test_a_silent_legacy_server_falls_back_after_the_probe_timeout():
    start = time.monotonic()
    with client("silent-legacy", probe_timeout_s=0.3) as c:
        assert c.era == "legacy"
        assert content_to_text(c.call_tool("echo", {"text": "hi"})) == "hi (via legacy)"
    assert time.monotonic() - start < 5


def test_a_dual_era_server_is_used_as_modern():
    with client("dual") as c:
        assert c.era == "modern"
        assert content_to_text(c.call_tool("echo", {"text": "hi"})) == "hi (via 2026-07-28)"


def test_an_unsupported_modern_version_is_an_error_not_a_fallback():
    c = client("future")
    try:
        with pytest.raises(McpError, match="2027-01-01"):
            c.connect()
        assert c.era != "legacy"
    finally:
        c.close()


def test_list_tools_follows_every_page():
    with client("modern") as c:
        assert [t["name"] for t in c.list_tools()] == ALL_NAMES


def test_endless_paging_is_capped():
    with client("endless") as c:
        with pytest.raises(McpError, match="100 pages"):
            c.list_tools()


def test_protocol_errors_raise_mcp_error():
    with client("modern") as c:
        with pytest.raises(McpError) as err:
            c.call_tool("nope", {})
        assert err.value.code == -32602 and "Unknown tool" in err.value.message


def test_input_required_results_are_refused():
    with client("modern") as c:
        with pytest.raises(McpError, match="input_required"):
            c.call_tool("ask", {})


def test_a_request_times_out():
    with client("modern", timeout_s=0.3) as c:
        with pytest.raises(McpTimeout):
            c.call_tool("sleep", {})


def test_a_crashed_server_is_a_connection_error():
    with client("crash") as c:
        with pytest.raises(ConnectionError):
            c.call_tool("echo", {"text": "x"})


def test_close_stops_the_server():
    c = client("modern")
    c.connect()
    c.close()
    assert c.transport.proc.poll() is not None


def test_the_server_gets_a_minimal_environment(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "hunter2")
    with McpClient.stdio([*SERVER, "modern"], env={"EXTRA": "1"}) as c:
        names = content_to_text(c.call_tool("env", {})).split(",")
    assert "SECRET_TOKEN" not in names and "EXTRA" in names and "PATH" in names


def test_content_to_text():
    result = {"content": [
        {"type": "text", "text": "hello"},
        {"type": "image", "data": "AAAA", "mimeType": "image/png"},
        {"type": "audio", "data": "AAAA", "mimeType": "audio/wav"},
        {"type": "resource_link", "uri": "file:///a.txt", "name": "a.txt"},
        {"type": "resource", "resource": {"uri": "file:///b.txt", "text": "inline b"}},
        {"type": "resource", "resource": {"uri": "file:///c.bin", "blob": "AAAA"}},
        {"type": "weird"},
    ]}
    assert content_to_text(result) == (
        "hello\n[image: image/png]\n[audio: audio/wav]\n[resource: file:///a.txt]\ninline b\n[resource: file:///c.bin]\n[weird content]"
    )
    assert content_to_text({"content": [], "structuredContent": {"a": 1}}) == '{"a": 1}'
    assert content_to_text({}) == ""


def test_tool_name_is_given():
    assert tool_name("files.read") == "files_read"
    assert tool_name("files.read", "my server") == "my_server__files_read"
    assert len(tool_name("x" * 100)) == 64


def test_mcp_tools_become_harnessy_tools():
    with client("modern") as c:
        tools = mcp_tools(c, prefix="fake")
        assert [t.name for t in tools] == [f"fake__{tool_name(n)}" for n in ALL_NAMES]
        by_name = {t.name: t for t in tools}
        assert by_name["fake__echo"].spec.parameters["required"] == ["text"]
        assert by_name["fake__files_read"].spec.description == "Read a file"
        assert by_name["fake__sleep"].spec.parameters == {"type": "object", "properties": {}}
        assert all(t.tags == ALL_TAGS for t in tools)
        registry = ToolRegistry(tools)
        assert registry.call(ToolCall("c1", "fake__echo", {"text": "yo"})).content == "yo (via 2026-07-28)"
        bad = registry.call(ToolCall("c2", "fake__echo", {}))
        assert bad.is_error and "missing required parameter 'text'" in bad.content
        failed = registry.call(ToolCall("c3", "fake__fail", {}))
        assert failed.is_error and "disk on fire" in failed.content
        assert mcp_tools(c, tags=())[0].tags == frozenset()


def test_an_agent_uses_mcp_tools_behind_an_approval_hook():
    with client("modern") as c:
        tools = mcp_tools(c, prefix="fake")
        with pytest.raises(TrifectaError):
            Agent(ScriptedModel([]), tools=tools)
        model = ScriptedModel([tool_reply(ToolCall("t1", "fake__echo", {"text": "hello"})), text_reply("done")])
        agent = Agent(model, tools=tools, hooks=[ApprovalHook({}, approver=lambda call: True, default="ask")])
        r = agent.run("echo hello")
        assert r.messages[2].tool_results[0].content == "hello (via 2026-07-28)" and r.stop_reason == "end_turn"
