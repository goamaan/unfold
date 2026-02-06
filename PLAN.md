# revengineer

An AI-powered reverse engineering assistant. Feed it a binary, it decompiles, annotates, explores, and explains — autonomously.

Think "Claude Code but for binaries."

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   CLI (revengineer)              │
│         Terminal UI / interactive REPL            │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│                  Agent Core                       │
│   Orchestrates the analysis loop:                │
│   1. User asks a question / gives a goal         │
│   2. Agent decides what tools to call            │
│   3. Reads decompiled output, reasons about it   │
│   4. Iterates until it has an answer             │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│              Tool Layer (MCP Server)             │
│                                                   │
│  Ghidra Headless Tools:                          │
│  ├── analyze_binary(path)     — run full analysis│
│  ├── list_functions()         — all functions    │
│  ├── decompile(func_name|addr)— get pseudocode  │
│  ├── get_xrefs_to(addr)       — who calls this? │
│  ├── get_xrefs_from(addr)     — what does it call│
│  ├── get_strings()            — all strings      │
│  ├── get_imports()            — imported symbols │
│  ├── get_exports()            — exported symbols │
│  ├── read_bytes(addr, n)      — raw hex dump     │
│  ├── get_data_at(addr)        — data type info   │
│  └── rename_function(addr, name) — annotate      │
│                                                   │
│  Utility Tools:                                  │
│  ├── run_binary(args)         — execute in sandbox│
│  ├── run_ltrace(path)         — library call trace│
│  ├── run_strace(path)         — syscall trace    │
│  ├── file_info(path)          — file/readelf/objdump│
│  └── search_memory(pattern)   — search binary    │
└─────────────────────────────────────────────────┘
```

## Tech Stack

- **Language:** Python (Ghidra scripting is Python/Java, and Python has the best RE library ecosystem)
- **LLM:** Claude API (via Anthropic SDK) with tool use
- **Decompiler:** Ghidra headless (`analyzeHeadless`) — free, scriptable, best decompiler available
- **CLI:** Rich or Textual for terminal UI
- **Sandboxing:** Docker container for running untrusted binaries safely
- **Alt decompiler (optional):** rizin/radare2 as a lighter-weight fallback

## Implementation Plan

### Phase 1: Foundation — Ghidra Bridge

**Goal:** Get Ghidra headless working as a callable service from Python.

**Files:**
```
revengineer/
├── pyproject.toml
├── src/
│   └── revengineer/
│       ├── __init__.py
│       ├── ghidra/
│       │   ├── __init__.py
│       │   ├── bridge.py          # Manages Ghidra headless process
│       │   ├── scripts/           # Ghidra Python scripts (run inside Ghidra's Jython)
│       │   │   ├── analyze.py     # Initial analysis
│       │   │   ├── decompile.py   # Decompile a function
│       │   │   ├── list_funcs.py  # List all functions
│       │   │   ├── xrefs.py       # Cross-references
│       │   │   ├── strings.py     # Extract strings
│       │   │   └── imports.py     # List imports/exports
│       │   └── project.py         # Manages Ghidra project files
│       └── utils.py
```

**How the Ghidra bridge works:**
1. `analyzeHeadless` is Ghidra's CLI — you pass it a binary and a script to run
2. The script runs inside Ghidra's Jython environment with access to the full Ghidra API
3. Scripts output JSON to stdout, which our Python code parses
4. We cache the Ghidra project so re-analysis isn't needed every time

**Tasks:**
- [ ] Set up project structure with pyproject.toml (uv-based)
- [ ] Write Ghidra Jython scripts for each operation
- [ ] Build `GhidraBridge` class that shells out to `analyzeHeadless` and parses results
- [ ] Add caching — Ghidra project files persist between runs
- [ ] Test with a simple "hello world" binary

### Phase 2: Tool Layer

**Goal:** Wrap the Ghidra bridge into clean tools the agent can call.

**Files:**
```
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── ghidra_tools.py    # Ghidra-backed tools
│       │   ├── dynamic_tools.py   # strace/ltrace/execution
│       │   └── file_tools.py      # file, readelf, objdump, strings
```

**Tools to implement:**

| Tool | Description | Backed by |
|------|-------------|-----------|
| `analyze_binary` | Load and fully analyze a binary | Ghidra headless |
| `list_functions` | List all functions with addresses and sizes | Ghidra |
| `decompile` | Decompile a specific function to pseudocode | Ghidra |
| `get_xrefs_to` | Find all callers of a function/address | Ghidra |
| `get_xrefs_from` | Find all callees from a function | Ghidra |
| `get_strings` | Extract all strings from the binary | Ghidra / `strings` |
| `get_imports` | List imported library functions | Ghidra |
| `get_exports` | List exported symbols | Ghidra |
| `read_bytes` | Hex dump at an address | Ghidra |
| `file_info` | Run `file`, `readelf -h`, basic binary info | CLI tools |
| `run_binary` | Execute the binary with given args (sandboxed) | Docker |
| `trace_calls` | Run with ltrace/strace | CLI tools |

**Tasks:**
- [ ] Define tool schemas (name, description, parameters, return type)
- [ ] Implement each tool as a Python function
- [ ] Add dynamic analysis tools (strace, ltrace) with Docker sandboxing
- [ ] Add `file_info` tool that combines `file`, `readelf`, `checksec` output

### Phase 3: Agent Core

**Goal:** Wire up Claude with tools so it can autonomously explore binaries.

**Files:**
```
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── core.py            # Main agent loop (Claude + tools)
│       │   ├── prompts.py         # System prompts for different modes
│       │   └── context.py         # Manages what the agent "knows" so far
```

**Agent loop:**
```python
# Simplified pseudocode
def run(binary_path, user_goal):
    tools = register_all_tools(binary_path)
    messages = [
        system_prompt(mode="explore"),  # or "solve_ctf", "find_vulns", etc.
        user_message(f"Analyze {binary_path}. Goal: {user_goal}")
    ]

    while True:
        response = claude.messages.create(
            model="claude-sonnet-4-5-20250929",
            tools=tools,
            messages=messages
        )

        # Process tool calls
        for tool_use in response.tool_calls:
            result = execute_tool(tool_use)
            messages.append(tool_result(result))

        # If Claude responded with text (no more tool calls), we're done
        if response.stop_reason == "end_turn":
            return response.text
```

**System prompt modes:**
- **Explore** — "Systematically analyze this binary. Identify its purpose, key functions, data structures, and interesting behaviors."
- **CTF Solve** — "Find the flag. Try to understand the validation logic and determine the correct input."
- **Vuln Hunt** — "Look for security vulnerabilities: buffer overflows, format strings, use-after-free, integer overflows, etc."
- **Annotate** — "Rename all functions and variables to meaningful names. Document what each function does."
- **Explain** — "Explain what this binary does at a high level, as if writing documentation for it."

**Tasks:**
- [ ] Implement the agent loop with Claude tool use
- [ ] Write system prompts for each mode
- [ ] Add context management (track what functions have been analyzed, build a mental map)
- [ ] Add conversation memory (the agent should remember what it already found)
- [ ] Handle token limits (summarize findings when context gets large)

### Phase 4: CLI Interface

**Goal:** Make it usable as a terminal tool.

**Files:**
```
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py            # CLI entry point
```

**Usage:**
```bash
# Interactive exploration
revengineer ./crackme01

# Specific goal
revengineer ./crackme01 --goal "find the password"

# Just annotate
revengineer ./malware.bin --mode annotate --output annotated.c

# CTF mode
revengineer ./challenge --mode ctf
```

**Tasks:**
- [ ] Build CLI with Click or Typer
- [ ] Add interactive REPL mode (ask follow-up questions)
- [ ] Add streaming output (see the agent's reasoning in real-time)
- [ ] Add output formats (annotated C, markdown report, JSON)

### Phase 5: Testing with Real Binaries

**Goal:** Validate that it actually works.

**Test targets (in order of difficulty):**

1. **Self-compiled binaries** — compile simple C programs, verify the agent can explain them
2. **crackmes.one easy tier** — simple password checks, XOR encoding
3. **picoCTF RE challenges** — well-structured, increasing difficulty
4. **Stripped binaries** — no symbols, agent must infer everything
5. **CTF challenge binaries** — from past CTF competitions
6. **Real malware samples** — from MalwareBazaar (in Docker only)

**Tasks:**
- [ ] Create a test suite of 10-20 binaries with known answers
- [ ] Build a benchmark harness (did the agent find the flag? did it correctly identify the algorithm?)
- [ ] Measure success rate across difficulty tiers
- [ ] Iterate on prompts and tool design based on failures

### Phase 6: Polish & Extras (stretch)

- [ ] **MCP server mode** — expose as an MCP server so it works inside Claude Code
- [ ] **Binary diffing** — compare two versions of a binary (patch analysis)
- [ ] **Angr integration** — symbolic execution to automatically find inputs that reach specific code paths
- [ ] **Hex-Rays / Binary Ninja support** — alternative decompiler backends
- [ ] **Auto-exploit generation** — for found vulnerabilities, generate proof-of-concept exploits
- [ ] **Report generation** — produce a full PDF/markdown analysis report

## Prerequisites

- **Ghidra** — `brew install --cask ghidra` or download from https://ghidra-sre.org
- **Java 17+** — required by Ghidra (`brew install openjdk@17`)
- **Python 3.11+**
- **Docker** — for sandboxed binary execution
- **Anthropic API key**

## Getting Started (first session)

```bash
# 1. Install Ghidra
brew install --cask ghidra

# 2. Set up the project
uv init
uv add anthropic rich click

# 3. Verify Ghidra headless works
analyzeHeadless /tmp/ghidra_project test_project -import ./test_binary -postScript ./scripts/list_funcs.py

# 4. Start building Phase 1
```

## Key Design Decisions

1. **Ghidra headless over r2/rizin** — Ghidra's decompiler output is significantly better, and it's what most professionals use. The headless mode is clunky but workable.

2. **Scripts-over-sockets for Ghidra** — Rather than running Ghidra as a server (which is fragile), we run short-lived headless scripts against a cached project. Slower per-call but much more reliable.

3. **Claude over GPT** — Claude handles long decompiled code better and is stronger at reasoning about code structure. Tool use support is also more reliable.

4. **Docker for dynamic analysis** — Never run untrusted binaries on the host. Even for CTF challenges, sandboxing is non-negotiable.

5. **Start with static analysis** — Dynamic analysis (strace, debugging) is Phase 2 priority. Static analysis alone can solve most RE tasks and is safer.
