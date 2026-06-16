"""Tests for the dispatcher safety gate."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import types

from devops_helper.dispatcher import dispatch, _response
from devops_helper.registry import Registry, ToolDefinition


def _make_registry(destructive: bool = False) -> Registry:
    registry = Registry()
    registry.register(ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters_json_schema={"type": "object", "properties": {}},
        mcp_server_id="test_server",
        destructive=destructive,
        group="test",
    ))
    return registry


def _make_function_call(name: str, args: dict | None = None) -> types.FunctionCall:
    fc = MagicMock(spec=types.FunctionCall)
    fc.name = name
    fc.args = args or {}
    return fc


@pytest.mark.asyncio
async def test_dispatch_read_only_executes_immediately():
    registry = _make_registry(destructive=False)
    mcp_manager = AsyncMock()
    mcp_manager.call_tool.return_value = "pod list output"

    fc = _make_function_call("test_tool", {"namespace": "default"})
    result = await dispatch(fc, registry, mcp_manager)

    mcp_manager.call_tool.assert_awaited_once_with("test_tool", {"namespace": "default"})
    assert result.name == "test_tool"
    assert result.response["result"] == "pod list output"


@pytest.mark.asyncio
async def test_dispatch_destructive_aborted():
    registry = _make_registry(destructive=True)
    mcp_manager = AsyncMock()

    fc = _make_function_call("test_tool", {"replicas": 0})

    with patch("devops_helper.dispatcher.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value="no")
        result = await dispatch(fc, registry, mcp_manager)

    mcp_manager.call_tool.assert_not_awaited()
    assert result.response["result"] == "Operation aborted by user."


@pytest.mark.asyncio
async def test_dispatch_destructive_confirmed():
    registry = _make_registry(destructive=True)
    mcp_manager = AsyncMock()
    mcp_manager.call_tool.return_value = "scaled successfully"

    fc = _make_function_call("test_tool", {"replicas": 3})

    with patch("devops_helper.dispatcher.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value="yes")
        result = await dispatch(fc, registry, mcp_manager)

    mcp_manager.call_tool.assert_awaited_once()
    assert result.response["result"] == "scaled successfully"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool():
    registry = _make_registry()
    mcp_manager = AsyncMock()

    fc = _make_function_call("nonexistent_tool")
    result = await dispatch(fc, registry, mcp_manager)

    assert "error" in result.response
    mcp_manager.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_tool_exception_returns_error():
    registry = _make_registry(destructive=False)
    mcp_manager = AsyncMock()
    mcp_manager.call_tool.side_effect = RuntimeError("MCP connection lost")

    fc = _make_function_call("test_tool")
    result = await dispatch(fc, registry, mcp_manager)

    # Exceptions are returned as a result string so Gemini can see the error
    assert "Error executing tool" in result.response.get("result", "")
    assert "MCP connection lost" in result.response.get("result", "")
