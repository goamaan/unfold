# unfold

**Claude Code, but for binaries.**

Point it at a binary. It decompiles, analyzes, and explains — autonomously.

```
$ unfold ./crackme --mode ctf --goal "find the password"
```

```
╭────────────────────────── unfold ──────────────────────────╮
│ Binary: crackme                                            │
│ Mode: ctf                                                  │
│ Goal: find the password                                    │
╰────────────────────────────────────────────────────────────╯

--- Turn 1/15 ---
  > analyze_binary
  > list_functions
  > get_strings         → found "hunter2" at 0x100000554

--- Turn 2/15 ---
  > decompile("_check_password")

    bool _check_password(char *param_1) {
        return strcmp(param_1, "hunter2") == 0;
    }

╭──────────────── Analysis Complete ─────────────────╮
│ The password is: hunter2                           │
╰────────────────────────────────────────────────────╯
```

## What it does

unfold gives an LLM autonomous access to Ghidra's decompiler. It can:

- **Decompile** any function to C pseudocode
- **Trace** cross-references and call graphs
- **Extract** strings, imports, and exports
- **Read** raw bytes at any address
- **Rename** functions as it understands them
- **Explain** everything it finds in plain English

Five analysis modes: `explore`, `ctf`, `vuln`, `annotate`, `explain`.

## Install

**Prerequisites:** [Ghidra 12+](https://github.com/NationalSecurityAgency/ghidra), Java 21+, Python 3.12+

```bash
# macOS
brew install ghidra

# Clone and install
git clone https://github.com/goamaan/unfold.git
cd unfold
uv sync  # or: pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# General exploration
unfold ./binary

# Solve a CTF challenge
unfold ./challenge --mode ctf

# Hunt for vulnerabilities
unfold ./target --mode vuln

# Specific goal
unfold ./binary --goal "find the encryption key"

# Annotate all functions with meaningful names
unfold ./binary --mode annotate

# Interactive mode — ask follow-up questions
unfold ./binary -i
```

### OpenAI-compatible endpoints

unfold also works with any OpenAI-compatible API proxy:

```bash
export CLIPROXY_BASE_URL=http://your-proxy:8080/v1
export CLIPROXY_API_KEY=your-key
unfold ./binary
```

## How it works

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────┐
│   CLI (unfold)   │────▶│  Agent Core  │────▶│  Ghidra (PyGhidra) │
│             │     │  Claude +     │     │  Decompile, xrefs, │
│  Rich TUI   │◀────│  tool use     │◀────│  strings, imports  │
└─────────────┘     └──────────────┘     └────────────────────┘
```

1. You give it a binary and a goal
2. Claude decides which Ghidra tools to call
3. It reads decompiled code, reasons about it, calls more tools
4. Repeats until it has an answer

The Ghidra integration uses [PyGhidra](https://github.com/NationalSecurityAgency/ghidra/tree/master/Ghidra/Features/PyGhidra) — Ghidra's Java API called directly from Python via JPype. No Jython, no subprocess shelling, no fragile script bridges.

## Tools

| Tool | Description |
|------|-------------|
| `analyze_binary` | Import and run Ghidra's full analysis |
| `list_functions` | List all functions with addresses and sizes |
| `decompile` | Decompile a function to C pseudocode |
| `get_xrefs_to` | Who calls this function? |
| `get_xrefs_from` | What does this function call? |
| `get_strings` | Extract all strings from the binary |
| `get_imports_exports` | List library imports and exports |
| `rename_function` | Rename a function to a meaningful name |
| `read_bytes` | Hex dump at any address |
| `file_info` | `file` command output |
| `binary_info` | `otool`/`readelf` headers |
| `raw_strings` | Unix `strings` extraction |
| `binary_size` | File size + MD5/SHA256 hashes |

## License

MIT
