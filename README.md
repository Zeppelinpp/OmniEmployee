# OmniEmployee

A powerful and extensible base agent system inspired by Anthropic's Agent Skills and MCP (Model Context Protocol) best practices.

## Features

- **Multi-Model Support**: Unified access to OpenAI, Anthropic, Google, DeepSeek, DashScope (Qwen), Ollama via LiteLLM
- **Progressive Disclosure**: Skills are discovered by metadata first, loaded on-demand to save context window
- **Reference Loading**: Skills can load additional reference files (e.g., error handling guides) on-demand
- **Modular Architecture**: Clean separation between Core, Tools, Context, and Skills
- **Built-in Tools**: grep (ripgrep), list_dir, read_file, write_file, run_command
- **Skill System**: Follows Anthropic's SKILL.md format with YAML frontmatter
- **Auto Path Injection**: Skill scripts automatically get full paths injected for correct execution
- **Context Management**: Smart compression and summarization for long conversations
- **Streaming Output**: Real-time response streaming with tool execution feedback
- **Environment Config**: Support for `.env` file configuration

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
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│  │
│  │  │  grep  │ │list_dir│ │read_file│ │write_file│ │run_cmd││  │
│  │  │(ripgrep)│ │  (fd)  │ │         │ │          │ │       ││  │
│  │  └────────┘ └────────┘ └────────┘ └────────────┘ └───────┘│  │
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

# Configure API keys (recommended: use .env file)
cp env.example .env
# Edit .env and add your API keys

# Or set environment variables directly
export OPENAI_API_KEY="your-key"      # For OpenAI
export ANTHROPIC_API_KEY="your-key"   # For Anthropic
export DASHSCOPE_API_KEY="your-key"   # For DashScope/Qwen
export DEEPSEEK_API_KEY="your-key"    # For DeepSeek
export GOOGLE_API_KEY="your-key"      # For Google/Gemini

# Run the agent (defaults to gpt-4o)
uv run python main.py

# Or specify a different model
MODEL=claude-sonnet-4-20250514 uv run python main.py
MODEL=qwen3-max uv run python main.py
MODEL=deepseek-chat uv run python main.py
MODEL=ollama/qwen2.5-coder uv run python main.py
```

### Supported Models

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1-preview, o1-mini |
| Anthropic | claude-sonnet-4-20250514, claude-3-5-sonnet, claude-3-opus |
| DashScope (Qwen) | qwen-turbo, qwen-plus, qwen-max, qwen3-max, qwen2.5-72b-instruct |
| Google | gemini-1.5-pro, gemini-1.5-flash |
| DeepSeek | deepseek-chat, deepseek-coder |
| Ollama | ollama/llama3, ollama/qwen2.5-coder, ollama/mistral |

## Project Structure

```
OmniEmployee/
├── src/
│   ├── omniemployee/
│   │   ├── core/           # Agent loop and orchestration
│   │   │   ├── agent.py    # Main Agent class
│   │   │   └── loop.py     # Execution loop
│   │   ├── tools/          # Built-in tools
│   │   │   ├── grep.py     # Code search (ripgrep)
│   │   │   ├── list_dir.py # Directory listing
│   │   │   ├── read_file.py # File reading
│   │   │   ├── write_file.py # File writing
│   │   │   └── run_command.py # Command execution
│   │   ├── context/        # Context management
│   │   │   ├── manager.py  # Progressive disclosure
│   │   │   └── message.py  # Message types
│   │   ├── skills/         # Skill management
│   │   │   ├── loader.py   # SKILL.md parser
│   │   │   ├── registry.py # Skill registry
│   │   │   └── models.py   # Skill data models
│   │   └── llm/            # LLM provider (LiteLLM)
│   │       └── provider.py # Unified LLM interface
│   ├── skills/             # User skills directory
│   │   └── book-flight/    # Example skill
│   │       ├── SKILL.md    # Main skill definition
│   │       ├── reference.md # Error handling & examples
│   │       └── scripts/     # Helper scripts
│   └── prompts/
│       └── system_prompt.md # System prompt template
├── .env                    # Environment variables (create from env.example)
├── env.example             # Environment template
├── main.py                 # Entry point
└── pyproject.toml         # Project configuration
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
src/skills/
└── my-skill/
    ├── SKILL.md           # Required: Main skill file with YAML frontmatter
    ├── reference.md        # Optional: Error handling, examples, detailed docs
    ├── forms.md           # Optional: Form definitions
    ├── scripts/           # Optional: Helper scripts
    │   └── helper.py      # Scripts automatically get full paths injected
    └── references/        # Optional: Additional reference files
        └── api.md
```

**Note**: When a skill is loaded, the system automatically injects:
- Skill directory path
- Full paths to all scripts with execution examples
- Available reference files that can be loaded on-demand

## Progressive Disclosure

The system implements progressive disclosure for efficient context management:

1. **Phase 1 - Discovery**: Only skill metadata is loaded initially (~100 tokens)
2. **Phase 2 - On-Demand Loading**: Full skill instructions loaded when needed (~5k tokens)
3. **Phase 3 - Reference Loading**: Additional reference files loaded when encountering errors or needing examples
4. **Phase 4 - Unloading**: Unused skills can be unloaded to free context space

```python
# Phase 1: Discover skills (metadata only)
agent.discover_skills()
# Output: Skill names and descriptions only

# Phase 2: Load skill when needed (Agent calls load_skill automatically)
agent.load_skill("book-flight")
# Output: Full SKILL.md instructions + script paths

# Phase 3: Load reference when encountering errors (Agent calls load_skill_reference)
agent.load_skill_reference("book-flight", "reference.md")
# Output: Error handling guides, examples, supported cities list

# Phase 4: Unload when done
agent.unload_skill("book-flight")
```

### Skill Management Tools

The Agent has access to these tools for skill management:

- **`load_skill(name)`**: Load full skill instructions
- **`load_skill_reference(skill_name, ref_path)`**: Load additional reference files (e.g., `reference.md`, `forms.md`)
- **`list_skills()`**: List all available skills with their status

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

### run_command

Execute shell commands or Python scripts:

```python
run_command(
    command="uv run scripts/get_current_time.py",  # Command to execute
    working_dir="src/skills/book-flight",          # Working directory (optional)
    timeout=120                                    # Timeout in seconds (optional)
)
```

**Use cases:**
- Execute skill scripts (paths are automatically injected when skill is loaded)
- Run system commands
- Execute Python scripts via `uv run`

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

Create a `.env` file (copy from `env.example`) or set environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-xxx` |
| `OPENAI_BASE_URL` | OpenAI API base URL | `https://api.openai.com/v1` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-xxx` |
| `ANTHROPIC_BASE_URL` | Anthropic API base URL | `https://api.anthropic.com` |
| `DASHSCOPE_API_KEY` | DashScope (Qwen) API key | `sk-xxx` |
| `DASHSCOPE_BASE_URL` | DashScope API base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | `sk-xxx` |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL | `https://api.deepseek.com/v1` |
| `GOOGLE_API_KEY` | Google/Gemini API key | `xxx` |
| `MODEL` | Override default model | `qwen3-max`, `gpt-4o` |
| `TEMPERATURE` | Override temperature | `0.7` |
| `MAX_ITERATIONS` | Override max iterations | `50` |
| `VERBOSE` | Show token usage | `1` |
| `DEBUG` | Show stack traces | `1` |

**Example `.env` file:**

```bash
# DashScope (Qwen)
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Default Model
MODEL=qwen3-max
TEMPERATURE=0.7
MAX_ITERATIONS=50
```

## Example: Book Flight Skill

The project includes a complete example skill (`src/skills/book-flight/`) demonstrating:

- **Progressive Disclosure**: Skill metadata → Full instructions → Reference files
- **Error Handling**: Agent automatically loads `reference.md` when encountering errors
- **Script Execution**: Scripts get full paths automatically injected
- **Multi-turn Interaction**: Agent guides users through incomplete booking requests

**Test the example:**

```bash
# Run the booking test
MODEL=qwen3-max uv run python test_booking.py

# Or test reference loading
MODEL=qwen3-max uv run python test_reference_loading.py
```

## Skill Development Tips

1. **Use relative paths in SKILL.md**: Script paths are automatically resolved
   ```markdown
   ```bash
   uv run scripts/get_current_time.py  # Relative path is fine
   ```
   ```

2. **Add error handling section**: Guide Agent to load reference.md when errors occur
   ```markdown
   ## Error Handling
   
   **IMPORTANT**: When encountering errors, load the reference:
   ```
   load_skill_reference("skill-name", "reference.md")
   ```
   ```

3. **Structure reference.md**: Include error solutions, examples, and supported values
   - Error handling strategies
   - Supported cities/values lists
   - Conversation examples
   - Script usage documentation

## License

MIT

