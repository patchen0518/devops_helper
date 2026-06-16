"""Async prompt_toolkit REPL."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from devops_helper.agent import Agent
from devops_helper.ui import console as ui

HISTORY_FILE = Path.home() / ".devops_helper_history"
EXIT_COMMANDS = {"exit", "quit", "\\q"}


async def run_repl(agent: Agent) -> None:
    session: PromptSession = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
    )

    ui.console.print("[dim]Type your question, 'exit' to quit, Ctrl+D to exit.[/dim]\n")

    while True:
        try:
            user_input = await session.prompt_async("[bold green]devops>[/bold green] ")
        except EOFError:
            ui.console.print("\n[dim]Goodbye.[/dim]")
            break
        except KeyboardInterrupt:
            ui.console.print("")
            continue

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() in EXIT_COMMANDS:
            ui.console.print("[dim]Goodbye.[/dim]")
            break

        try:
            response = await agent.turn(stripped)
            ui.print_response(response)
        except Exception as e:
            ui.print_error(str(e))
