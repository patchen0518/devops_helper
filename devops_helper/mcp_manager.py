"""MCP server lifecycle management: start, discover tools, call tools, stop."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as McpTool

from devops_helper.config import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict
    server_id: str


class MCPManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._tool_to_server: dict[str, str] = {}
        self._tool_infos: list[ToolInfo] = []
        self._exit_stack = contextlib.AsyncExitStack()

    async def start(self, server_configs: dict[str, ServerConfig]) -> None:
        """Connect to all configured MCP servers and discover their tools."""
        for server_id, cfg in server_configs.items():
            try:
                await self._connect_server(server_id, cfg)
            except Exception as e:
                logger.warning("Failed to connect to MCP server '%s': %s", server_id, e)

    async def _connect_server(self, server_id: str, cfg: ServerConfig) -> None:
        params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=cfg.env or None,
        )
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        result = await session.list_tools()
        tools: list[McpTool] = result.tools

        self._sessions[server_id] = session
        for tool in tools:
            name = tool.name
            if name in self._tool_to_server:
                # Prefix with server_id to resolve collision
                name = f"{server_id}__{tool.name}"
                logger.warning(
                    "Tool name collision: '%s' from server '%s' renamed to '%s'",
                    tool.name, server_id, name,
                )
            self._tool_to_server[name] = server_id
            self._tool_infos.append(ToolInfo(
                name=name,
                description=tool.description or "",
                input_schema=(
                    tool.inputSchema.model_dump()
                    if hasattr(tool.inputSchema, "model_dump")
                    else dict(tool.inputSchema)
                ),
                server_id=server_id,
            ))

        logger.info("Connected to '%s': %d tools registered", server_id, len(tools))

    def list_all_tools(self) -> list[ToolInfo]:
        return list(self._tool_infos)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        server_id = self._tool_to_server.get(tool_name)
        if server_id is None:
            return f"Error: unknown tool '{tool_name}'"

        original_name = tool_name
        if "__" in tool_name and tool_name.startswith(f"{server_id}__"):
            original_name = tool_name[len(server_id) + 2:]

        session = self._sessions[server_id]
        result = await session.call_tool(original_name, arguments=arguments)

        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))

        output = "\n".join(parts)
        return _truncate(output)

    async def stop(self) -> None:
        await self._exit_stack.aclose()

    async def __aenter__(self) -> "MCPManager":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())


def _truncate(text: str, max_chars: int = 8000) -> str:
    if len(text) <= max_chars:
        return text
    lines = text.split("\n")
    kept, char_count = [], 0
    for line in reversed(lines):
        if char_count + len(line) + 1 > max_chars:
            break
        kept.append(line)
        char_count += len(line) + 1
    omitted = len(lines) - len(kept)
    result = "\n".join(reversed(kept))
    return f"[{omitted} lines truncated]\n{result}"
