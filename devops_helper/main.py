"""CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from devops_helper.agent import Agent
from devops_helper.config import load_config
from devops_helper.mcp_manager import MCPManager
from devops_helper.registry import build_registry
from devops_helper.ui import console as ui
from devops_helper.ui.repl import run_repl


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="devops-helper",
        description="AI-powered DevOps CLI agent",
    )
    parser.add_argument(
        "--one-shot", "-q",
        metavar="QUERY",
        help="Run a single query and exit",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        help="Override Gemini model (e.g. gemini-2.5-pro)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    config = load_config()

    if args.model:
        config.gemini_model = args.model

    if not config.gemini_api_key:
        ui.print_error(
            "No Gemini API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
        )
        sys.exit(1)

    async with MCPManager() as mcp_manager:
        await mcp_manager.start(config.mcp_servers)

        registry = build_registry(mcp_manager, config)
        agent = Agent(registry, mcp_manager, config)

        if mcp_manager.connected_servers:
            ui.print_startup_banner(mcp_manager.connected_servers)
        else:
            ui.console.print(
                "[yellow]Warning: no MCP servers connected. "
                "Configure .devops-helper.yaml[/yellow]"
            )

        if args.one_shot:
            response = await agent.turn(args.one_shot)
            ui.print_response(response)
        else:
            await run_repl(agent)


def main() -> None:
    args = _parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
