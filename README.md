# OmniEmployee

A powerful AI agent system with bio-inspired memory and knowledge learning capabilities.

## Features

| Category | Features |
|----------|----------|
| **Agent Core** | Multi-model LLM support (OpenAI, Anthropic, DeepSeek, Qwen, Ollama) |
| **Skill System** | Progressive disclosure, on-demand loading, Anthropic SKILL.md format |
| **Memory (BIEM)** | Multi-tier storage (L1/L2/L3), energy decay, associative recall, LLM-powered consolidation |
| **Knowledge** | Global knowledge graph, triple extraction, conflict detection, cluster-based retrieval |
| **Tools** | grep, list_dir, read_file, write_file, run_command, web_search |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           OmniEmployee                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Agent Loop (Core)                            │ │
│  │  User Input → Context Injection → LLM Call → Tool Execution → Loop │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│          ┌─────────────────────────┼─────────────────────────┐          │
│          ▼                         ▼                         ▼          │
│  ┌──────────────┐      ┌───────────────────┐      ┌──────────────────┐ │
│  │    Tools     │      │  Context Manager  │      │  Skills Library  │ │
│  │  grep, read  │      │  Memory + Knowledge│      │  SKILL.md format │ │
│  │  write, run  │      │  injection        │      │  Progressive load│ │
│  └──────────────┘      └───────────────────┘      └──────────────────┘ │
│                                    │                                     │
│          ┌─────────────────────────┼─────────────────────────┐          │
│          ▼                         ▼                         ▼          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    BIEM Memory System (Per-User 👤)               │  │
│  │  ┌─────────┐    ┌─────────────────┐    ┌───────────────────────┐ │  │
│  │  │L1 Cache │ ←→ │L2 Vector + Graph│ ←→ │L3 Crystal (PostgreSQL)│ │  │
│  │  │(Dict)   │    │(Milvus+NetworkX)│    │Facts + Links          │ │  │
│  │  └─────────┘    └─────────────────┘    └───────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                 Knowledge System (Global 🌐)                      │  │
│  │  Triple Store (PostgreSQL) + Vector Index (Milvus)                │  │
│  │  LLM Extraction → Conflict Detection → Cluster Retrieval          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install
uv sync

# Configure (copy env.example to .env and add API keys)
cp env.example .env

# Run CLI
uv run python main.py

# Run Web UI + API
uv run uvicorn src.omniemployee.web.app:app --port 8765

# Run GUI (Rust/GPUI)
cd gui && cargo run --release
```

### Supported Models

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, o1-preview |
| Anthropic | claude-sonnet-4-20250514, claude-3-5-sonnet |
| DashScope | qwen-turbo, qwen-plus, qwen-max, qwen3-max |
| DeepSeek | deepseek-chat, deepseek-coder |
| Ollama | ollama/llama3, ollama/qwen2.5-coder |

## Memory System (BIEM)

Bio-Inspired Evolving Memory with energy decay and associative recall.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Memory Data Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input ──→ recall() ──→ Context Injection ──→ LLM Call     │
│       │                                               │          │
│       │                                               ▼          │
│       └──────────────────────────────────────→ ingest()         │
│                                                       │          │
│                                                       ▼          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Encoder → Energy → Conflict (LLM) → Store → Link        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│    ┌─────────┐        ┌───────────┐        ┌───────────┐       │
│    │   L1    │        │    L2     │        │    L3     │       │
│    │ Working │   ←→   │  Vector   │   →    │  Crystal  │       │
│    │ Memory  │        │  + Graph  │        │  (Facts)  │       │
│    └─────────┘        └───────────┘        └───────────┘       │
│    energy≥0.5          Always              Consolidation        │
│                                            (LLM refine)         │
└─────────────────────────────────────────────────────────────────┘
```

| Layer | Storage | Trigger | Content |
|-------|---------|---------|---------|
| **L1** | Python Dict | `energy >= 0.5` | Hot cache |
| **L2 Vector** | Milvus | Always | All embeddings |
| **L2 Graph** | NetworkX | Always | Node links (temporal/semantic) |
| **L3 Links** | PostgreSQL | Link creation | Persistent edges |
| **L3 Facts** | PostgreSQL | Background task | LLM-refined crystals |

📖 **Details**: [docs/memory_system.md](docs/memory_system.md)

## Knowledge System

Global knowledge graph with LLM-powered extraction and conflict detection.

```
User: "GPT-4 has 128k context window"
         │
         ▼
┌─────────────────────────────────────┐
│  LLM Extraction                     │
│  → (GPT-4, context_window, 128k)    │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Conflict Detection                 │
│  Existing: (GPT-4, context_window, 32k)
│  → Prompt user for confirmation     │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Storage (Global 🌐)                │
│  PostgreSQL + Milvus Vector Index   │
└─────────────────────────────────────┘
```

| Feature | Description |
|---------|-------------|
| **Extraction** | LLM extracts (subject, predicate, object) triples |
| **Conflict** | Detects updates to existing knowledge |
| **Retrieval** | Cluster expansion for related knowledge |
| **Scope** | Global (shared across all users) |

📖 **Details**: [docs/memory_system.md#知识学习系统](docs/memory_system.md#知识学习系统-knowledge-learning)

## Project Structure

```
OmniEmployee/
├── src/
│   ├── omniemployee/
│   │   ├── core/           # Agent loop
│   │   ├── tools/          # Built-in tools
│   │   ├── context/        # Context management
│   │   ├── skills/         # Skill loader
│   │   ├── llm/            # LLM provider (LiteLLM)
│   │   ├── memory/         # BIEM memory system
│   │   │   ├── storage/    # L1, L2, L3 backends
│   │   │   ├── operators/  # Encoder, Energy, Conflict, Router
│   │   │   └── knowledge/  # Knowledge extraction & store
│   │   └── web/            # FastAPI web UI
│   ├── skills/             # User skills (SKILL.md)
│   └── prompts/            # LLM prompt templates
├── gui/                    # Rust/GPUI native client
├── docs/                   # Documentation
│   └── memory_system.md    # BIEM technical docs
└── main.py                 # CLI entry point
```

## Configuration

### Environment Variables

```bash
# LLM Providers
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DASHSCOPE_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx

# Storage (Memory & Knowledge)
POSTGRES_HOST=localhost
POSTGRES_DB=biem
MILVUS_HOST=localhost

# Runtime
MODEL=gpt-4o
USER_ID=default
```

### Services

```bash
# Start Milvus
docker compose -f docker-compose.milvus.yml up -d

# Start PostgreSQL
brew services start postgresql@18
psql -c "CREATE DATABASE biem;"
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/memory_system.md](docs/memory_system.md) | BIEM memory system technical details |
| [src/prompts/](src/prompts/) | LLM prompt templates |
| [src/skills/](src/skills/) | Example skills (SKILL.md format) |

## License

MIT
