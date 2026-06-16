"""Tool dispatch: safety gate + MCP routing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.genai import types

from devops_helper.mcp_manager import MCPManager
from devops_helper.registry import Registry
from devops_helper.ui import console as ui

logger = logging.getLogger(__name__)


async def dispatch(
    function_call: types.FunctionCall,
    registry: Registry,
    mcp_manager: MCPManager,
) -> types.FunctionResponse:
    name = function_call.name
    args: dict[str, Any] = dict(function_call.args) if function_call.args else {}

    td = registry.get(name)
    if td is None:
        return _response(name, error=f"Unknown tool: {name}")

    ui.print_tool_call(name, args)

    if td.destructive:
        ui.print_plan_panel(name, td.mcp_server_id, args)
        try:
            confirmed = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("  Type 'yes' to confirm, anything else to abort: ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            confirmed = ""

        if confirmed != "yes":
            result = "Operation aborted by user."
            ui.print_tool_result(name, result)
            return _response(name, result=result)

    try:
        result = await mcp_manager.call_tool(name, args)
    except Exception as e:
        logger.exception("Tool '%s' raised an exception", name)
        result = f"Error executing tool: {e}"

    ui.print_tool_result(name, result)
    return _response(name, result=result)


async def dispatch_all(
    function_calls: list[types.FunctionCall],
    registry: Registry,
    mcp_manager: MCPManager,
) -> list[types.FunctionResponse]:
    # Run non-destructive calls concurrently; run destructive ones sequentially
    # to avoid interleaved confirmation prompts.
    destructive = [fc for fc in function_calls if _is_destructive(fc.name, registry)]
    read_only = [fc for fc in function_calls if not _is_destructive(fc.name, registry)]

    results: list[types.FunctionResponse] = []

    # Read-only in parallel
    if read_only:
        results.extend(
            await asyncio.gather(
                *[dispatch(fc, registry, mcp_manager) for fc in read_only]
            )
        )

    # Destructive sequentially
    for fc in destructive:
        results.append(await dispatch(fc, registry, mcp_manager))

    return results


def _is_destructive(name: str, registry: Registry) -> bool:
    td = registry.get(name)
    return td.destructive if td else False


def _response(
    name: str, *, result: str | None = None, error: str | None = None
) -> types.FunctionResponse:
    payload = {"result": result} if result is not None else {"error": error}
    return types.FunctionResponse(name=name, response=payload)
