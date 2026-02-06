"""CLI entry point for unfold."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("binary", type=click.Path(exists=True))
@click.option(
    "--mode", "-m",
    type=click.Choice(["explore", "ctf", "vuln", "annotate", "explain"]),
    default="explore",
    help="Analysis mode",
)
@click.option("--goal", "-g", type=str, default=None, help="Specific analysis goal")
@click.option(
    "--model",
    type=str,
    default="claude-sonnet-4-5-20250929",
    help="Claude model to use",
)
@click.option("--max-turns", type=int, default=50, help="Max agent turns")
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive REPL after analysis")
def main(binary: str, mode: str, goal: str | None, model: str, max_turns: int, interactive: bool):
    """unfold — AI-powered reverse engineering assistant.

    Analyze BINARY using Claude and Ghidra.

    Examples:

        unfold ./crackme01

        unfold ./crackme01 --goal "find the password"

        unfold ./challenge --mode ctf

        unfold ./malware.bin --mode vuln

        unfold ./binary --mode explain

        unfold ./binary -i  (interactive mode)
    """
    # Set JAVA_HOME if not set
    os.environ.setdefault(
        "JAVA_HOME",
        "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
    )

    binary_path = Path(binary).resolve()

    console.print(f"[bold blue]unfold[/bold blue] v0.1.0")
    console.print(f"Loading [bold]{binary_path.name}[/bold]...")
    console.print()

    try:
        from unfold.agent import Agent

        agent = Agent(
            binary_path=binary_path,
            mode=mode,
            model=model,
            max_turns=max_turns,
        )

        # Run initial analysis
        result = agent.run(goal=goal)

        # Interactive REPL
        if interactive:
            console.print("\n[bold]Entering interactive mode.[/bold] Type 'quit' or 'exit' to stop.\n")
            while True:
                try:
                    question = console.input("[bold blue]> [/bold blue]")
                    if question.strip().lower() in ("quit", "exit", "q"):
                        break
                    if not question.strip():
                        continue
                    agent.ask(question)
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Goodbye.[/dim]")
                    break

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if os.environ.get("UNFOLD_DEBUG"):
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
