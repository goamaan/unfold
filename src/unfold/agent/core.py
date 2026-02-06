"""Core agent loop for binary analysis."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from unfold.agent.prompts import get_system_prompt
from unfold.ghidra.bridge import GhidraBridge
from unfold.tools import get_all_tools, execute_tool

logger = logging.getLogger(__name__)
console = Console()


def _make_openai_tools(tool_defs: list[dict]) -> list[dict]:
    """Convert our tool definitions to OpenAI function calling format."""
    openai_tools = []
    for td in tool_defs:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": td["name"],
                "description": td["description"],
                "parameters": td["input_schema"],
            },
        })
    return openai_tools


class Agent:
    """Reverse engineering agent powered by Claude."""

    def __init__(
        self,
        binary_path: Path,
        mode: str = "explore",
        model: str | None = None,
        max_turns: int = 50,
        project_dir: Path | None = None,
    ):
        self.binary_path = Path(binary_path).resolve()
        if not self.binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {self.binary_path}")

        self.mode = mode
        self.max_turns = max_turns

        # Detect backend: OpenAI-compatible proxy vs native Anthropic
        cliproxy_url = os.environ.get("CLIPROXY_BASE_URL")
        cliproxy_key = os.environ.get("CLIPROXY_API_KEY")

        if cliproxy_url and cliproxy_key:
            self._backend = "openai"
            self.model = model or "claude-sonnet-4-5-20250929"
            from openai import OpenAI
            self._openai = OpenAI(base_url=cliproxy_url, api_key=cliproxy_key)
            logger.info("Using OpenAI-compatible proxy at %s", cliproxy_url)
        else:
            self._backend = "anthropic"
            self.model = model or "claude-sonnet-4-5-20250929"
            import anthropic
            self._anthropic = anthropic.Anthropic()
            logger.info("Using native Anthropic API")

        # Initialize Ghidra bridge and tools
        self.bridge = GhidraBridge(project_dir=project_dir)
        tool_defs, self.handler_map = get_all_tools(self.bridge, self.binary_path)
        self._tool_defs = tool_defs

        # System prompt
        self.system_prompt = get_system_prompt(mode)

        # Conversation history
        self.messages: list[dict] = []

    def _call_anthropic(self, messages):
        return self._anthropic.messages.create(
            model=self.model,
            max_tokens=16384,
            system=self.system_prompt,
            tools=self._tool_defs,
            messages=messages,
        )

    def _call_openai(self, messages):
        openai_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in messages:
            openai_messages.append(self._convert_to_openai_msg(msg))
        return self._openai.chat.completions.create(
            model=self.model,
            max_tokens=16384,
            tools=_make_openai_tools(self._tool_defs),
            messages=openai_messages,
        )

    def _convert_to_openai_msg(self, msg: dict) -> dict:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            return {"role": role, "content": content}

        if isinstance(content, list):
            # Could be tool results or content blocks
            if role == "user":
                # Check if these are tool results
                if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                    # OpenAI uses separate "tool" messages
                    # Return a list of messages
                    return [
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr["content"],
                        }
                        for tr in content
                    ]

            # Anthropic content blocks -> text
            if role == "assistant":
                text_parts = []
                tool_calls = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            })
                result = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return result

        return {"role": role, "content": str(content)}

    def run(self, goal: str | None = None) -> str:
        if goal:
            user_msg = f"Analyze the binary at `{self.binary_path.name}`. Goal: {goal}"
        else:
            user_msg = f"Analyze the binary at `{self.binary_path.name}`."

        self.messages = [{"role": "user", "content": user_msg}]

        console.print(Panel(
            f"[bold]Binary:[/bold] {self.binary_path.name}\n"
            f"[bold]Mode:[/bold] {self.mode}\n"
            f"[bold]Goal:[/bold] {goal or 'General analysis'}\n"
            f"[bold]Model:[/bold] {self.model}\n"
            f"[bold]Backend:[/bold] {self._backend}",
            title="[bold blue]unfold[/bold blue]",
            border_style="blue",
        ))

        if self._backend == "anthropic":
            return self._run_anthropic(self.messages)
        else:
            return self._run_openai(self.messages)

    def _run_anthropic(self, messages: list[dict]) -> str:
        for turn in range(self.max_turns):
            console.print(f"\n[dim]--- Turn {turn + 1}/{self.max_turns} ---[/dim]")

            response = self._call_anthropic(messages)
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn":
                final_text = ""
                for block in assistant_content:
                    if block.type == "text":
                        final_text += block.text
                console.print("\n")
                console.print(Panel(Markdown(final_text), title="[bold green]Analysis Complete[/bold green]", border_style="green"))
                return final_text

            tool_results = []
            for block in assistant_content:
                if block.type == "text":
                    console.print(f"[cyan]{block.text}[/cyan]")
                elif block.type == "tool_use":
                    self._print_tool_call(block.name, block.input)
                    result = execute_tool(self.handler_map, block.name, block.input)
                    if len(result) > 30000:
                        result = result[:30000] + "\n... (truncated)"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                    self._print_tool_result(result)

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        return "Analysis incomplete — reached maximum number of turns."

    def _run_openai(self, messages: list[dict]) -> str:
        openai_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in messages:
            converted = self._convert_to_openai_msg(msg)
            if isinstance(converted, list):
                openai_messages.extend(converted)
            else:
                openai_messages.append(converted)

        openai_tools = _make_openai_tools(self._tool_defs)

        for turn in range(self.max_turns):
            console.print(f"\n[dim]--- Turn {turn + 1}/{self.max_turns} ---[/dim]")

            response = self._openai.chat.completions.create(
                model=self.model,
                max_tokens=16384,
                tools=openai_tools,
                messages=openai_messages,
            )

            choice = response.choices[0]
            msg = choice.message

            # Add assistant message
            assistant_msg = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            openai_messages.append(assistant_msg)

            if choice.finish_reason == "stop" or not msg.tool_calls:
                final_text = msg.content or ""
                if msg.content:
                    console.print(f"[cyan]{msg.content}[/cyan]")
                console.print("\n")
                console.print(Panel(Markdown(final_text), title="[bold green]Analysis Complete[/bold green]", border_style="green"))
                return final_text

            # Process tool calls
            if msg.content:
                console.print(f"[cyan]{msg.content}[/cyan]")

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    tool_input = {}

                self._print_tool_call(tool_name, tool_input)
                result = execute_tool(self.handler_map, tool_name, tool_input)
                if len(result) > 30000:
                    result = result[:30000] + "\n... (truncated)"
                self._print_tool_result(result)

                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return "Analysis incomplete — reached maximum number of turns."

    def ask(self, question: str) -> str:
        """Ask a follow-up question (continues the conversation)."""
        self.messages.append({"role": "user", "content": question})
        if self._backend == "anthropic":
            return self._run_anthropic(self.messages)
        else:
            return self._run_openai(self.messages)

    def _print_tool_call(self, name: str, input_data: dict):
        console.print(f"  [yellow]> {name}[/yellow]", end="")
        if input_data:
            compact = json.dumps(input_data)
            if len(compact) > 80:
                compact = compact[:77] + "..."
            console.print(f"[dim]({compact})[/dim]", end="")
        console.print()

    def _print_tool_result(self, result: str):
        preview = result[:200]
        if len(result) > 200:
            preview += "..."
        console.print(f"    [dim]{preview}[/dim]")
