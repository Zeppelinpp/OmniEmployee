# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Running Single Agent

```bash
# Run with default model (gpt-4o)
uv run python main.py

# Run with specific model
MODEL=qwen-plus uv run python main.py
MODEL=claude-sonnet-4-20250514 uv run python main.py
MODEL=deepseek-chat uv run python main.py
MODEL=ollama/qwen2.5-coder uv run python main.py

# Single prompt mode (run and exit)
PROMPT="your question here" uv run python main.py

# Verbose mode (show token usage)
VERBOSE=1 uv run python main.py

# Debug mode (show stack traces)
DEBUG=1 uv run python main.py
```

### Running Multi-Agent System

```bash
# Run multi-agent system
uv run python multiagent_main.py

# Or with specific model
MODEL=qwen-plus uv run python multiagent_main.py
```

### Environment Setup

```bash
# Install dependencies
uv sync

# Configure API keys (copy template and edit)
cp env.example .env
# Edit .env file with your API keys

# Set environment variables directly
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export DASHSCOPE_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
```

## High-Level Architecture

OmniEmployee is a modular AI agent system implementing progressive disclosure for efficient context management.

### Core Components

**Agent** (`src/omniemployee/core/agent.py`): The main orchestrator that manages context, tools, and skills.

**AgentLoop** (`src/omniemployee/core/loop.py`): Execution engine that runs the agent loop - calls LLM, executes tools, handles streaming, manages skill loading/unloading, and triggers context compression when needed.

**ContextManager** (`src/omniemployee/context/manager.py`): Manages conversation context with progressive disclosure and smart compression.

**ToolRegistry** (`src/omniemployee/tools/registry.py`): Registry for managing and executing tools.

**SkillRegistry** (`src/omniemployee/skills/`): Implements three-phase progressive disclosure system for skills.

**LLMProvider** (`src/omniemployee/llm/provider.py`): Unified LLM interface using LiteLLM.

### Skill System

Skills are located in `src/skills/` and follow Anthropic's format:

```
src/skills/my-skill/
├── SKILL.md           # Main skill definition (required)
├── reference.md       # Error handling, examples (optional)
├── forms.md           # Form definitions (optional)
├── scripts/           # Helper scripts (optional)
│   └── helper.py
└── references/        # Additional documentation (optional)
    └── api.md
```

### Progressive Disclosure

Three-phase skill loading:
1. **Phase 1**: Discovery - loads only skill metadata (~100 words, always in context)
2. **Phase 2**: On-demand loading - loads full SKILL.md instructions (<5k words)
3. **Phase 3**: Reference loading - loads additional files (reference.md, forms.md, references/*)

### Built-in Tools

Located in `src/omniemployee/tools/`:
- `grep`: Code search using ripgrep
- `list_dir`: Directory listing
- `read_file`: File reading with line ranges
- `write_file`: File writing (overwrite/append/insert)
- `run_command`: Execute shell commands or Python scripts
- `web_search`: Web search using Tavily API
- `web_extract`: Extract content from web pages

### Multi-Agent System (NEW)

**`AgentOrchestrator`** (`src/omniemployee/multiagent/orchestrator.py`): Manages multiple agents working collaboratively

**`MessageBroker`** (`src/omniemployee/multiagent/message_broker.py`): Pub-sub messaging for agent communication

**`SharedContext`** (`src/omniemployee/multiagent/shared_context.py`): Manages shared state accessible to all agents

### Multi-Agent Architecture

```
AgentOrchestrator
├── MessageBroker (pub-sub messaging)
├── SharedContext (shared task progress/state)
└── Multiple Agent instances
    ├── ContextManager (private context per agent)
    ├── ToolRegistry (shared across all agents)
    ├── SkillRegistry (independent per agent)
    └── AgentLoop (with progress callbacks)
```

### Key Multi-Agent Features

1. **Independent Context**: Each agent maintains its own private conversation context
2. **Partial Sharing**: SharedContext provides:
   - Task progress from all agents
   - Global state (key-value pairs)
   - Active task list
3. **Pub-Sub Communication**: Agents communicate via topics (e.g., "tasks", "coordination", "results")
4. **Progress Reporting**: Agents use `report_progress()` to update shared context
5. **Communication Tools**:
   - `report_progress(task_id, status, progress, message)`
   - `send_message(agent_id, topic, message_type, content)`
   - `get_messages(topic, limit)`
6. **Shared Tools**: All agents share the same ToolRegistry
7. **Rich Output**: Status and progress displayed with clean text styling

### Multi-Agent Workflow

1. Orchestrator initializes from configuration
2. Creates shared resources (ToolRegistry, MessageBroker, SharedContext)
3. Initializes each agent with its skills and model
4. Agents subscribe to relevant topics
5. User submits task to orchestrator
6. Task is created in SharedContext and broadcast to all agents
7. Agents execute their subtasks independently
8. Agents report progress using `report_progress` tool
9. SharedContext aggregates progress from all agents
10. ContextManager injects shared context into each agent's system prompt
11. Agents see overall progress and adjust their plans
12. Orchestrator returns final result when all complete

### Multi-Agent Configuration

**`config/multiagent.yaml`**: Multi-agent system configuration

```yaml
agents:
  - id: "coordinator"
    name: "Task Coordinator"
    role: "planner and coordinator"
    skills: ["task-planning"]
    model: "gpt-4o"

  - id: "researcher"
    name: "Research Agent"
    role: "researcher"
    skills: ["research", "web-search"]
    required_tools: ["web_search", "web_extract", "grep", "read_file"]
    model: "claude-sonnet-4-20250514"

  - id: "developer"
    name: "Developer Agent"
    role: "developer"
    skills: ["codebase-tools"]
    required_tools: ["grep", "read_file", "write_file", "run_command"]
    model: "deepseek-chat"

workspace_root: "."
skills_dir: "src/skills"
share_tools: true
coordination_strategy: "collaborative"  # "autonomous", "orchestrated", or "collaborative"
```

### File Structure

```
OmniEmployee/
├── config/
│   ├── multiagent.yaml         # Multi-agent configuration
│   └── env.example
├── src/omniemployee/
│   ├── core/
│   │   ├── agent.py          # Modified: supports agent_id, shared_context, message_broker
│   │   └── loop.py           # Modified: adds progress callbacks and communication tools
│   ├── context/
│   │   └── manager.py       # Modified: injects shared context
│   ├── tools/
│   │   └── registry.py       # Can be shared across agents
│   ├── multiagent/            # NEW: Multi-agent collaboration
│   │   ├── models.py
│   │   ├── message.py
│   │   ├── message_broker.py
│   │   ├── shared_context.py
│   │   ├── orchestrator.py
│   │   ├── config.py
│   │   └── __init__.py
│   └── skills/             # Independent skill registry per agent
├── src/skills/                # Agent skills
│   ├── research/
│   └── codebase-tools/
├── prompts/
│   ├── system_prompt.md
│   └── agent_coordinator.md  # Coordinator agent prompt
├── main.py                    # Single agent entry
└── multiagent_main.py        # Multi-agent entry point (NEW)
```

### Model Detection

LLMProvider auto-detects provider from model name pattern:
- `gpt-*`, `o1-*`, `o3-*` → OpenAI (`OPENAI_API_KEY`)
- `claude-*` → Anthropic (`ANTHROPIC_API_KEY`)
- `qwen-*`, `qwen2`, `qwen3` → DashScope (`DASHSCOPE_API_KEY`)
- `deepseek-*` → DeepSeek (`DEEPSEEK_API_KEY`)
- `gemini-*` → Google (`GOOGLE_API_KEY`)
- `ollama/*` → Ollama (`OLLAMA_BASE_URL`)
- `groq/*` → Groq (`GROQ_API_KEY`)
- `together/*` → Together (`TOGETHER_API_KEY`)

Context window is auto-detected via LiteLLM's `model_cost` dict, falling back to 128000.
