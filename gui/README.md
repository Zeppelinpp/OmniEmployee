# OmniEmployee GUI

A beautiful desktop GUI for OmniEmployee AI Assistant, built with [GPUI](https://github.com/zed-industries/zed) (Zed's GPU-accelerated UI framework) and featuring the **Monokai Pro** color scheme.

## Features

- 🎨 **Monokai Pro Theme** - Dark theme with vibrant accent colors
- 💬 **Chat Interface** - Clean message bubbles with role indicators
- 📦 **Collapsible Panels** - View Memory, Knowledge, and Tool Use in the sidebar
- ⌨️ **Command System** - Use `/commands` to access CLI-like features
- ⚙️ **Configurable** - Show/hide panels via configuration

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/stats` | Show agent statistics (model, provider, tools) |
| `/memory` | Show memory system statistics |
| `/knowledge` | Show learned knowledge triples |
| `/clear` | Clear conversation history |
| `/reconnect` | Reconnect to the backend API |
| `/config <key> <value>` | Update configuration |

### Configuration Keys

- `show_memory` - Show/hide Memory panel (`true`/`false`)
- `show_knowledge` - Show/hide Knowledge panel (`true`/`false`)
- `show_tools` - Show/hide Tool Use panel (`true`/`false`)

## Screenshots

The app features:
- **Header**: Logo, title, and status indicators for Memory/Knowledge
- **Messages Panel**: Scrollable chat with User (green), Assistant (cyan), System (yellow) messages
- **Sidebar**: Collapsible panels for Tool Use (🔧), Memory (🧠), and Knowledge (📚)
- **Input Bar**: Text input with Send button and command hints

## Building

### Prerequisites

- Rust 1.70+ (nightly recommended for GPUI)
- macOS (GPUI currently supports macOS only, Linux/Windows support in development)

### Build & Run

```bash
cd gui
cargo build --release
cargo run
```

## Architecture

```
gui/
├── Cargo.toml          # Dependencies
├── README.md           # This file
└── src/
    ├── main.rs         # Application entry, App struct, Render implementation
    ├── theme/
    │   └── mod.rs      # Monokai Pro color palette and theme configuration
    └── api/
        └── mod.rs      # API client for communicating with Python backend
```

## Theme Colors (Monokai Pro)

| Color | Hex | Usage |
|-------|-----|-------|
| Background | `#2d2a2e` | Main background |
| Background Dark | `#19181a` | Secondary/elevated |
| Foreground | `#fcfcfa` | Main text |
| Red/Pink | `#ff6188` | Errors, warnings |
| Orange | `#fc9867` | Tool use accent |
| Yellow | `#ffd866` | System messages |
| Green | `#a9dc76` | Success, user messages, knowledge |
| Cyan | `#78dce8` | Assistant messages, links, focus |
| Purple | `#ab9df2` | Memory accent |

## Integration with OmniEmployee

The GUI is designed to work with the OmniEmployee Python backend. **Full setup:**

### 1. Start the Backend API

```bash
# From the project root
uv run uvicorn src.omniemployee.web.app:app --port 8765
```

This starts the FastAPI server with:
- Chat API (`/api/chat`) - Real conversation with the agent
- Memory API (`/api/memory/context`, `/api/stats`) - BIEM memory system
- Knowledge API (`/api/knowledge/triples`, `/api/knowledge/stats`) - Knowledge triples
- Agent Info API (`/api/agent/info`) - Model, skills, tools info

### 2. Run the GUI

```bash
cd gui && cargo run --release
```

### 3. Interact

- Type messages to chat with the AI agent
- The sidebar shows real Tool Use, Memory, and Knowledge data
- Click panel headers to expand/collapse
- Use `/commands` for quick actions

### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat` | Send message, get response with tool calls |
| `GET /api/agent/info` | Get model, provider, skills, tools |
| `GET /api/memory/context` | Retrieve relevant memories |
| `GET /api/stats` | Memory system statistics |
| `GET /api/knowledge/triples` | All knowledge triples |
| `GET /api/knowledge/stats` | Knowledge statistics |
| `POST /api/chat/clear` | Clear conversation |

## License

MIT
