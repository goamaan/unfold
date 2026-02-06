"""CLI entry point for unfold."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console

from unfold.config import load_config

console = Console()


@click.command()
@click.argument("binary", type=click.Path(exists=True), required=False)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["explore", "ctf", "vuln", "annotate", "explain"]),
    default=None,
    help="Analysis mode",
)
@click.option("--goal", "-g", type=str, default=None, help="Specific analysis goal")
@click.option("--model", type=str, default=None, help="Claude model to use")
@click.option("--max-turns", type=int, default=None, help="Max agent turns")
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive REPL after analysis")
@click.option("--stream/--no-stream", default=None, help="Enable/disable streaming output")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "html"]),
    default=None,
    help="Report output format",
)
@click.option("--save-session", is_flag=True, default=False, help="Save session after analysis")
@click.option(
    "--resume", type=click.Path(exists=True), default=None, help="Resume from session file"
)
@click.option("--list-sessions", is_flag=True, default=False, help="List saved sessions")
def main(
    binary: str | None,
    mode: str | None,
    goal: str | None,
    model: str | None,
    max_turns: int | None,
    interactive: bool,
    stream: bool | None,
    output: str | None,
    output_format: str | None,
    save_session: bool,
    resume: str | None,
    list_sessions: bool,
):
    """unfold -- AI-powered reverse engineering assistant.

    Analyze BINARY using Claude and Ghidra.

    Examples:

        unfold ./crackme01

        unfold ./crackme01 --goal "find the password"

        unfold ./challenge --mode ctf

        unfold ./malware.bin --mode vuln

        unfold ./binary --mode explain

        unfold ./binary -i  (interactive mode)

        unfold ./binary --stream  (streaming output)

        unfold ./binary -o report.md  (save Markdown report)

        unfold ./binary -o report.json --format json  (save JSON report)

        unfold ./binary --save-session  (save session for later)

        unfold --resume ~/.unfold/sessions/latest.json -i  (resume session)

        unfold --list-sessions  (list saved sessions)
    """
    # Handle --list-sessions
    if list_sessions:
        from unfold.session import list_sessions as _list_sessions

        _list_sessions(console)
        return

    # Load config with CLI overrides
    cli_overrides: dict = {}
    if model is not None:
        cli_overrides["model"] = model
    if max_turns is not None:
        cli_overrides["max_turns"] = max_turns
    if output is not None:
        cli_overrides["output_file"] = output
    if output_format is not None:
        cli_overrides["output_format"] = output_format
    if stream is not None:
        cli_overrides["stream"] = stream

    config = load_config(cli_overrides=cli_overrides)

    # Default stream to True when TTY, False when piped
    if stream is None and config.stream:
        config.stream = sys.stdout.isatty()

    # Set JAVA_HOME from config if needed
    if config.java_home:
        os.environ.setdefault("JAVA_HOME", config.java_home)
    else:
        os.environ.setdefault(
            "JAVA_HOME",
            "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
        )

    # Handle --resume
    if resume:
        console.print("[bold blue]unfold[/bold blue] v0.2.0")
        console.print(f"Resuming session from [bold]{resume}[/bold]...")
        console.print()

        try:
            from unfold.agent import Agent

            agent = Agent.from_session(resume, config=config)

            if interactive:
                console.print(
                    "\n[bold]Entering interactive mode.[/bold] Type 'quit' or 'exit' to stop.\n"
                )
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

            if save_session:
                from unfold.session import save_session as _save_session

                session_path = _save_session(agent)
                console.print(f"\n[dim]Session saved to {session_path}[/dim]")

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            if os.environ.get("UNFOLD_DEBUG"):
                raise
            sys.exit(1)
        return

    # Require binary for non-resume, non-list-sessions commands
    if not binary:
        raise click.UsageError("Missing argument 'BINARY'. Provide a binary path to analyze.")

    binary_path = Path(binary).resolve()
    mode = mode or "explore"

    console.print("[bold blue]unfold[/bold blue] v0.2.0")
    console.print(f"Loading [bold]{binary_path.name}[/bold]...")
    console.print()

    try:
        from unfold.agent import Agent

        agent = Agent(
            binary_path=binary_path,
            mode=mode,
            model=config.model_for_mode(mode) if model is None else model,
            max_turns=config.max_turns,
            config=config,
            stream=config.stream,
        )

        # Run initial analysis
        result = agent.run(goal=goal)

        # Save report if requested
        if config.output_file:
            from unfold.report import Report

            report = Report.from_agent(agent, result, goal=goal)
            fmt = config.output_format if config.output_format != "terminal" else None

            # Auto-detect format from extension
            if fmt is None and config.output_file:
                ext = Path(config.output_file).suffix.lower()
                fmt = {".json": "json", ".html": "html", ".md": "markdown"}.get(ext, "markdown")

            output_path = Path(config.output_file)
            if fmt == "json":
                output_path.write_text(report.to_json())
            elif fmt == "html":
                output_path.write_text(report.to_html())
            else:
                output_path.write_text(report.to_markdown())

            console.print(f"\n[dim]Report saved to {output_path}[/dim]")

        # Save session if requested
        if save_session:
            from unfold.session import save_session as _save_session

            session_path = _save_session(agent)
            console.print(f"\n[dim]Session saved to {session_path}[/dim]")

        # Interactive REPL
        if interactive:
            console.print(
                "\n[bold]Entering interactive mode.[/bold] Type 'quit' or 'exit' to stop.\n"
            )
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

            # Save session after interactive if requested
            if save_session:
                from unfold.session import save_session as _save_session

                session_path = _save_session(agent)
                console.print(f"\n[dim]Session saved to {session_path}[/dim]")

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
