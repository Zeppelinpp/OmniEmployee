# OmniEmployee

A powerful and extensible base agent system inspired by Anthropic's Agent Skills and MCP (Model Context Protocol) best practices.

## Features

- **Multi-Model Support**: Unified access to OpenAI, Anthropic, Google, DeepSeek, Ollama via LiteLLM
- **Progressive Disclosure**: Skills are discovered by metadata first, loaded on-demand to save context window
- **Modular Architecture**: Clean separation between Core, Tools, Context, and Skills
- **Built-in Tools**: grep (ripgrep), list_dir, read_file, write_file
- **Skill System**: Follows Anthropic's SKILL.md format with YAML frontmatter
- **Context Management**: Smart compression and summarization for long conversations
- **Streaming Output**: Real-time response streaming with tool execution feedback

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OmniEmployee                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Agent Loop (Core)                   │    │
│  │  • Task planning and execution                       │    │
│  │  • Tool orchestration                                │    │
│  │  • Skill loading (progressive disclosure)            │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌───────────────────────────┼───────────────────────────┐  │
│  │                    Tool Layer                          │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │  │
│  │  │  grep  │ │list_dir│ │read_file│ │write_file│        │  │
│  │  │(ripgrep)│ │  (fd)  │ │         │ │          │        │  │
│  │  └────────┘ └────────┘ └────────┘ └────────────┘        │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────┼───────────────────────────┐  │
│  │              Context Management                        │  │
│  │  • Progressive skill loading                           │  │
│  │  • Smart compression                                   │  │
│  │  • Token budget management                             │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────┼───────────────────────────┐  │
│  │                   Skills Library                       │  │
│  │  skills/                                               │  │
│  │  └── codebase-tools/                                   │  │
│  │      ├── SKILL.md          # Main skill definition     │  │
│  │      ├── advanced-search.md # Additional docs          │  │
│  │      ├── scripts/          # Helper scripts            │  │
│  │      └── resources/        # YAML/JSON resources       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- ripgrep (`brew install ripgrep`)
- fd (optional, `brew install fd`)
- API key for your chosen provider

### Installation

```bash
# Clone the repository
cd OmniEmployee

# Install dependencies
uv sync

# Set your API key (choose one)
export OPENAI_API_KEY="your-key"      # For OpenAI
export ANTHROPIC_API_KEY="your-key"   # For Anthropic
export GOOGLE_API_KEY="your-key"      # For Google/Gemini
export DEEPSEEK_API_KEY="your-key"    # For DeepSeek

# Run the agent (defaults to gpt-4o)
uv run python main.py

# Or specify a different model
MODEL=claude-sonnet-4-20250514 uv run python main.py
MODEL=deepseek-chat uv run python main.py
MODEL=ollama/qwen2.5-coder uv run python main.py
```

### Supported Models

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1-preview |
| Anthropic | claude-sonnet-4-20250514, claude-3-5-sonnet, claude-3-opus |
| Google | gemini-1.5-pro, gemini-1.5-flash |
| DeepSeek | deepseek-chat, deepseek-coder |
| Ollama | ollama/llama3, ollama/qwen2.5-coder, ollama/mistral |

## Project Structure

```
OmniEmployee/
├── omniemployee/
│   ├── core/           # Agent loop and orchestration
│   │   ├── agent.py    # Main Agent class
│   │   └── loop.py     # Execution loop
│   ├── tools/          # Built-in tools
│   │   ├── grep.py     # Code search (ripgrep)
│   │   ├── list_dir.py # Directory listing
│   │   ├── read_file.py # File reading
│   │   └── write_file.py # File writing
│   ├── context/        # Context management
│   │   ├── manager.py  # Progressive disclosure
│   │   └── message.py  # Message types
│   └── skills/         # Skill management
│       ├── loader.py   # SKILL.md parser
│       └── registry.py # Skill registry
├── skills/             # User skills directory
│   └── codebase-tools/ # Example skill
│       └── SKILL.md
├── configs/
│   └── agent.yaml      # Configuration
└── main.py             # Entry point
```

## Creating Skills

Skills follow Anthropic's format with YAML frontmatter:

```markdown
---
name: my-skill
description: What this skill does
license: MIT
version: 1.0.0
tags: [tag1, tag2]
when_to_use: When to activate this skill
required_tools: [grep, read_file]
required_packages: []
---

# Skill Instructions

Your detailed instructions here...
```

### Skill Directory Structure

```
skills/
└── my-skill/
    ├── SKILL.md           # Required: Main skill file
    ├── additional-docs.md # Optional: Extra documentation
    ├── scripts/           # Optional: Helper scripts
    │   └── helper.py
    └── resources/         # Optional: YAML/JSON data
        └── config.yaml
```

## Progressive Disclosure

The system implements progressive disclosure for efficient context management:

1. **Phase 1 - Discovery**: Only skill metadata is loaded initially
2. **Phase 2 - On-Demand Loading**: Full skill instructions loaded when needed
3. **Phase 3 - Unloading**: Unused skills can be unloaded to free context space

```python
# Phase 1: Discover skills (metadata only)
agent.discover_skills()

# Phase 2: Load skill when needed
agent.load_skill("codebase-tools")

# Phase 3: Unload when done
agent.unload_skill("codebase-tools")
```

## Context Management

The context manager handles:

- **Token Budgeting**: Tracks estimated token usage
- **Smart Compression**: Summarizes old messages when approaching limits
- **Tool Result Summarization**: Truncates long tool outputs
- **Skill Budget**: Limits tokens per loaded skill

## Built-in Tools

### grep (ripgrep)

```python
grep(
    pattern="def __init__",  # Regex pattern
    path="src/",             # Search path
    file_type="py",          # File type filter
    context_lines=2,         # Context lines
    max_results=50           # Result limit
)
```

### list_dir

```python
list_dir(
    path="src/",      # Directory path
    depth=2,          # Recursion depth
    pattern="*.py",   # Glob filter
    show_hidden=False # Show hidden files
)
```

### read_file

```python
read_file(
    path="main.py",   # File path
    start_line=10,    # Start line (1-based)
    end_line=50,      # End line
    max_lines=500     # Max lines to return
)
```

### write_file

```python
write_file(
    path="new.py",           # File path
    content="...",           # Content
    mode="overwrite",        # overwrite/append/insert/replace_lines
    start_line=10,           # For insert/replace_lines
    end_line=20              # For replace_lines
)
```

## Agent Loop

The agent loop follows this execution pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Loop Flow                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Input ──▶ Add to Context                               │
│                     │                                        │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LLM Call (via LiteLLM)                   │   │
│  │  • Messages + Tools + Loaded Skills                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                     │                                        │
│          ┌─────────┴─────────┐                              │
│          ▼                   ▼                              │
│    Tool Calls?          Final Response                      │
│          │                   │                              │
│          ▼                   ▼                              │
│  ┌───────────────┐    ┌───────────────┐                    │
│  │ Execute Tools │    │ Return to User│                    │
│  │ Add Results   │    └───────────────┘                    │
│  └───────────────┘                                          │
│          │                                                   │
│          └──────────▶ Loop back to LLM                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Loop States

| State | Description |
|-------|-------------|
| `IDLE` | Waiting for user input |
| `THINKING` | LLM is generating response |
| `TOOL_CALLING` | Executing tool calls |
| `COMPLETED` | Task finished successfully |
| `ERROR` | An error occurred |
| `MAX_ITERATIONS` | Hit iteration limit |

## Configuration

See `configs/agent.yaml` for full configuration options:

```yaml
# LLM Configuration (LiteLLM)
llm:
  model: "gpt-4o"  # or claude-sonnet-4-20250514, deepseek-chat, etc.
  temperature: 0.7
  max_tokens: 4096

# Loop Configuration
loop:
  max_iterations: 50
  max_tool_calls_per_turn: 10
  auto_load_skills: true

# Context Management
context:
  max_tokens: 128000
  skill_token_budget: 8000
  compress_threshold: 0.8

tools:
  grep:
    max_results: 50
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GOOGLE_API_KEY` | Google/Gemini API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `MODEL` | Override model from config |
| `TEMPERATURE` | Override temperature |
| `MAX_ITERATIONS` | Override max iterations |
| `API_BASE` | Custom API base URL |
| `VERBOSE` | Show token usage |
| `DEBUG` | Show stack traces |

## License

MIT

