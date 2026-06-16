"""Rich console singleton and print helpers."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_response(text: str) -> None:
    console.print(Markdown(text))


def print_tool_call(name: str, args: dict) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    for k, v in args.items():
        table.add_row(f"[dim]{k}[/dim]", str(v))
    console.print(
        Panel(table, title=f"[cyan]tool: {name}[/cyan]", border_style="cyan", expand=False)
    )


def print_tool_result(name: str, result: str) -> None:
    preview = result[:300] + "..." if len(result) > 300 else result
    console.print(f"[dim]← {name}:[/dim] {preview}\n")


def print_plan_panel(tool_name: str, server_id: str, args: dict) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold]Tool[/bold]", tool_name)
    table.add_row("[bold]Server[/bold]", server_id)
    table.add_row("", "")
    for k, v in args.items():
        table.add_row(f"[yellow]{k}[/yellow]", str(v))
    console.print(
        Panel(table, title="[yellow bold]PLANNED OPERATION[/yellow bold]", border_style="yellow")
    )


def print_error(msg: str) -> None:
    console.print(f"[red]Error:[/red] {msg}")


def print_startup_banner(servers: list[str]) -> None:
    console.print(
        Panel(
            f"[green]Connected servers:[/green] {', '.join(servers) if servers else 'none'}",
            title="[bold]DevOps Helper[/bold]",
            border_style="green",
        )
    )
