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
from unfold.agent.usage import UsageTracker
from unfold.config import Config
from unfold.ghidra.bridge import GhidraBridge
from unfold.tools import execute_tool, get_all_tools

logger = logging.getLogger(__name__)
console = Console()


def _make_openai_tools(tool_defs: list[dict]) -> list[dict]:
    """Convert our tool definitions to OpenAI function calling format."""
    openai_tools = []
    for td in tool_defs:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": td["name"],
                    "description": td["description"],
                    "parameters": td["input_schema"],
                },
            }
        )
    return openai_tools


class Agent:
    """Reverse engineering agent powered by Claude."""

    def __init__(
        self,
        binary_path: Path,
        mode: str = "explore",
        model: str | None = None,
        max_turns: int | None = None,
        project_dir: Path | None = None,
        config: Config | None = None,
        stream: bool | None = None,
    ):
        self.config = config or Config()
        self.binary_path = Path(binary_path).resolve()
        if not self.binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {self.binary_path}")

        self.mode = mode
        self.max_turns = max_turns if max_turns is not None else self.config.max_turns
        self.stream = stream if stream is not None else self.config.stream

        # Resolve model: explicit arg > mode_models > config default
        if model:
            self.model = model
        else:
            self.model = self.config.model_for_mode(mode)

        # Detect backend: OpenAI-compatible proxy vs native Anthropic
        cliproxy_url = os.environ.get("CLIPROXY_BASE_URL")
        cliproxy_key = os.environ.get("CLIPROXY_API_KEY")

        if cliproxy_url and cliproxy_key:
            self._backend = "openai"
            from openai import OpenAI

            self._openai = OpenAI(base_url=cliproxy_url, api_key=cliproxy_key)
            logger.info("Using OpenAI-compatible proxy at %s", cliproxy_url)
        else:
            self._backend = "anthropic"
            import anthropic

            self._anthropic = anthropic.Anthropic(max_retries=3)
            logger.info("Using native Anthropic API")

        # Initialize Ghidra bridge and tools
        resolved_project_dir = project_dir or self.config.resolved_project_dir
        self.bridge = GhidraBridge(
            project_dir=resolved_project_dir,
            ghidra_install_dir=self.config.ghidra_install_dir,
            java_home=self.config.java_home,
        )
        tool_defs, self.handler_map = get_all_tools(self.bridge, self.binary_path)
        self._tool_defs = tool_defs

        # System prompt
        self.system_prompt = get_system_prompt(mode)

        # Conversation history
        self.messages: list[dict] = []

        # Usage tracking
        self.usage = UsageTracker(model=self.model)

        # Turn data for report building
        self.turn_data: list[dict] = []

    def _call_anthropic(self, messages):
        response = self._anthropic.messages.create(
            model=self.model,
            max_tokens=self.config.max_tokens,
            system=self.system_prompt,
            tools=self._tool_defs,
            messages=messages,
        )
        self.usage.add_anthropic(response)
        return response

    def _call_openai(self, messages):
        openai_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in messages:
            converted = self._convert_to_openai_msg(msg)
            if isinstance(converted, list):
                openai_messages.extend(converted)
            else:
                openai_messages.append(converted)
        response = self._openai.chat.completions.create(
            model=self.model,
            max_tokens=self.config.max_tokens,
            tools=_make_openai_tools(self._tool_defs),
            messages=openai_messages,
        )
        self.usage.add_openai(response)
        return response

    def _convert_to_openai_msg(self, msg: dict) -> dict | list:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            return {"role": role, "content": content}

        if isinstance(content, list):
            if role == "user":
                if (
                    content
                    and isinstance(content[0], dict)
                    and content[0].get("type") == "tool_result"
                ):
                    return [
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr["content"],
                        }
                        for tr in content
                    ]

            if role == "assistant":
                text_parts = []
                tool_calls = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": json.dumps(block.input),
                                    },
                                }
                            )
                result = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return result

        return {"role": role, "content": str(content)}

    def run(self, goal: str | None = None) -> str:
        """Run analysis on the binary."""
        if goal:
            user_msg = f"Analyze the binary at `{self.binary_path.name}`. Goal: {goal}"
        else:
            user_msg = f"Analyze the binary at `{self.binary_path.name}`."

        self.messages = [{"role": "user", "content": user_msg}]
        self.turn_data = []

        console.print(
            Panel(
                f"[bold]Binary:[/bold] {self.binary_path.name}\n"
                f"[bold]Mode:[/bold] {self.mode}\n"
                f"[bold]Goal:[/bold] {goal or 'General analysis'}\n"
                f"[bold]Model:[/bold] {self.model}\n"
                f"[bold]Backend:[/bold] {self._backend}",
                title="[bold blue]unfold[/bold blue]",
                border_style="blue",
            )
        )

        if self._backend == "anthropic":
            if self.stream:
                result = self._run_anthropic_streaming(self.messages)
            else:
                result = self._run_anthropic(self.messages)
        else:
            if self.stream:
                result = self._run_openai_streaming(self.messages)
            else:
                result = self._run_openai(self.messages)

        # Print usage summary
        console.print(
            Panel(
                self.usage.summary(),
                title="[bold]Token Usage[/bold]",
                border_style="dim",
            )
        )

        return result

    def _truncate(self, text: str) -> str:
        """Truncate tool result to configured limit."""
        limit = self.config.truncation_limit
        if len(text) > limit:
            return text[:limit] + "\n... (truncated)"
        return text

    def _run_anthropic(self, messages: list[dict]) -> str:
        """Non-streaming Anthropic agent loop."""
        for turn in range(self.max_turns):
            console.print(f"\n[dim]--- Turn {turn + 1}/{self.max_turns} ---[/dim]")

            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = self._call_anthropic(messages)

            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            turn_record = {"turn": turn + 1, "text": "", "tool_calls": []}

            if response.stop_reason == "end_turn":
                final_text = ""
                for block in assistant_content:
                    if block.type == "text":
                        final_text += block.text
                turn_record["text"] = final_text
                self.turn_data.append(turn_record)
                console.print("\n")
                console.print(
                    Panel(
                        Markdown(final_text),
                        title="[bold green]Analysis Complete[/bold green]",
                        border_style="green",
                    )
                )
                return final_text

            tool_results = []
            for block in assistant_content:
                if block.type == "text":
                    turn_record["text"] += block.text
                    console.print(f"[cyan]{block.text}[/cyan]")
                elif block.type == "tool_use":
                    self._print_tool_call(block.name, block.input)
                    result = execute_tool(self.handler_map, block.name, block.input)
                    result = self._truncate(result)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result}
                    )
                    turn_record["tool_calls"].append(
                        {"name": block.name, "input": block.input, "result": result[:500]}
                    )
                    self._print_tool_result(result)

            self.turn_data.append(turn_record)
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        return "Analysis incomplete — reached maximum number of turns."

    def _run_anthropic_streaming(self, messages: list[dict]) -> str:
        """Streaming Anthropic agent loop."""
        for turn in range(self.max_turns):
            console.print(f"\n[dim]--- Turn {turn + 1}/{self.max_turns} ---[/dim]")

            turn_record = {"turn": turn + 1, "text": "", "tool_calls": []}

            # Stream the response
            content_blocks: list = []
            current_text = ""
            current_tool_name = ""
            current_tool_id = ""
            current_tool_json = ""

            with self._anthropic.messages.stream(
                model=self.model,
                max_tokens=self.config.max_tokens,
                system=self.system_prompt,
                tools=self._tool_defs,
                messages=messages,
            ) as stream:
                for event in stream:
                    event_type = event.type

                    if event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "text":
                            current_text = ""
                        elif block.type == "tool_use":
                            current_tool_name = block.name
                            current_tool_id = block.id
                            current_tool_json = ""

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            console.print(delta.text, end="")
                            current_text += delta.text
                        elif delta.type == "input_json_delta":
                            current_tool_json += delta.partial_json

                    elif event_type == "content_block_stop":
                        if current_text:
                            content_blocks.append(
                                type("TextBlock", (), {"type": "text", "text": current_text})()
                            )
                            turn_record["text"] += current_text
                            current_text = ""
                        if current_tool_name:
                            try:
                                tool_input = (
                                    json.loads(current_tool_json) if current_tool_json else {}
                                )
                            except json.JSONDecodeError:
                                tool_input = {}
                            content_blocks.append(
                                type(
                                    "ToolUseBlock",
                                    (),
                                    {
                                        "type": "tool_use",
                                        "id": current_tool_id,
                                        "name": current_tool_name,
                                        "input": tool_input,
                                    },
                                )()
                            )
                            current_tool_name = ""
                            current_tool_json = ""

                # Get final response for usage tracking
                final_response = stream.get_final_message()
                self.usage.add_anthropic(final_response)
                stop_reason = final_response.stop_reason

            messages.append({"role": "assistant", "content": final_response.content})

            if stop_reason == "end_turn":
                final_text = ""
                for block in final_response.content:
                    if block.type == "text":
                        final_text += block.text
                turn_record["text"] = final_text
                self.turn_data.append(turn_record)
                console.print("\n")
                console.print(
                    Panel(
                        Markdown(final_text),
                        title="[bold green]Analysis Complete[/bold green]",
                        border_style="green",
                    )
                )
                return final_text

            # Execute tool calls
            tool_results = []
            for block in final_response.content:
                if block.type == "tool_use":
                    console.print()
                    self._print_tool_call(block.name, block.input)
                    result = execute_tool(self.handler_map, block.name, block.input)
                    result = self._truncate(result)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result}
                    )
                    turn_record["tool_calls"].append(
                        {"name": block.name, "input": block.input, "result": result[:500]}
                    )
                    self._print_tool_result(result)

            self.turn_data.append(turn_record)
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        return "Analysis incomplete — reached maximum number of turns."

    def _run_openai(self, messages: list[dict]) -> str:
        """Non-streaming OpenAI agent loop."""
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

            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = self._openai.chat.completions.create(
                    model=self.model,
                    max_tokens=self.config.max_tokens,
                    tools=openai_tools,
                    messages=openai_messages,
                )
            self.usage.add_openai(response)

            choice = response.choices[0]
            msg = choice.message

            turn_record = {"turn": turn + 1, "text": msg.content or "", "tool_calls": []}

            assistant_msg: dict = {"role": "assistant", "content": msg.content}
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
                turn_record["text"] = final_text
                self.turn_data.append(turn_record)
                console.print("\n")
                console.print(
                    Panel(
                        Markdown(final_text),
                        title="[bold green]Analysis Complete[/bold green]",
                        border_style="green",
                    )
                )
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
                result = self._truncate(result)
                self._print_tool_result(result)

                turn_record["tool_calls"].append(
                    {"name": tool_name, "input": tool_input, "result": result[:500]}
                )

                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

            self.turn_data.append(turn_record)

        return "Analysis incomplete — reached maximum number of turns."

    def _run_openai_streaming(self, messages: list[dict]) -> str:
        """Streaming OpenAI agent loop."""
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

            turn_record = {"turn": turn + 1, "text": "", "tool_calls": []}

            # Collect streamed response
            collected_text = ""
            collected_tool_calls: dict[int, dict] = {}
            finish_reason = None

            stream = self._openai.chat.completions.create(
                model=self.model,
                max_tokens=self.config.max_tokens,
                tools=openai_tools,
                messages=openai_messages,
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    # Usage chunk at the end
                    if chunk.usage:
                        self.usage.input_tokens += getattr(chunk.usage, "prompt_tokens", 0)
                        self.usage.output_tokens += getattr(chunk.usage, "completion_tokens", 0)
                        self.usage.api_calls += 1
                    continue

                delta = chunk.choices[0].delta
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

                if delta.content:
                    console.print(delta.content, end="")
                    collected_text += delta.content

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            collected_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                collected_tool_calls[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                collected_tool_calls[idx]["arguments"] += (
                                    tc_delta.function.arguments
                                )

            turn_record["text"] = collected_text

            # Build assistant message
            assistant_msg: dict = {"role": "assistant", "content": collected_text or None}
            if collected_tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in sorted(collected_tool_calls.values(), key=lambda x: x["id"])
                ]
            openai_messages.append(assistant_msg)

            if finish_reason == "stop" or not collected_tool_calls:
                turn_record["text"] = collected_text
                self.turn_data.append(turn_record)
                console.print("\n")
                console.print(
                    Panel(
                        Markdown(collected_text),
                        title="[bold green]Analysis Complete[/bold green]",
                        border_style="green",
                    )
                )
                return collected_text

            # Execute tool calls
            for tc in sorted(collected_tool_calls.values(), key=lambda x: x["id"]):
                tool_name = tc["name"]
                try:
                    tool_input = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    tool_input = {}

                console.print()
                self._print_tool_call(tool_name, tool_input)
                result = execute_tool(self.handler_map, tool_name, tool_input)
                result = self._truncate(result)
                self._print_tool_result(result)

                turn_record["tool_calls"].append(
                    {"name": tool_name, "input": tool_input, "result": result[:500]}
                )

                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            self.turn_data.append(turn_record)

        return "Analysis incomplete — reached maximum number of turns."

    def ask(self, question: str) -> str:
        """Ask a follow-up question (continues the conversation)."""
        self.messages.append({"role": "user", "content": question})
        if self._backend == "anthropic":
            if self.stream:
                return self._run_anthropic_streaming(self.messages)
            return self._run_anthropic(self.messages)
        else:
            if self.stream:
                return self._run_openai_streaming(self.messages)
            return self._run_openai(self.messages)

    @classmethod
    def from_session(cls, session_path: str | Path, config: Config | None = None) -> Agent:
        """Restore an Agent from a saved session file."""
        from unfold.session import load_session

        data = load_session(session_path)

        binary_path = Path(data["binary_path"])
        if not binary_path.exists():
            raise FileNotFoundError(
                f"Binary from session not found: {binary_path}. "
                "Ensure the binary is still at the original path."
            )

        agent = cls(
            binary_path=binary_path,
            mode=data.get("mode", "explore"),
            model=data.get("model"),
            max_turns=data.get("max_turns"),
            config=config,
            stream=data.get("stream"),
        )

        # Restore conversation history (only simple serializable messages)
        agent.messages = [
            msg for msg in data.get("messages", []) if isinstance(msg.get("content"), (str, list))
        ]
        agent.turn_data = data.get("turn_data", [])

        return agent

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
