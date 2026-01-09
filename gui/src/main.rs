//! OmniEmployee GUI - A beautiful AI assistant interface
//!
//! Built with GPUI and Monokai Pro theme

mod api;
mod theme;

use api::{ApiClient, KnowledgeTriple, MemoryItem, StreamEvent, ToolCall};
use gpui::{
    actions, anchored, deferred, div, prelude::FluentBuilder, px, size, AppContext, Application, Bounds,
    ClickEvent, Context, Entity, FontWeight, Hsla, InteractiveElement,
    IntoElement, ParentElement, Render, SharedString,
    StatefulInteractiveElement, Styled, TitlebarOptions, Window, WindowBounds,
    WindowOptions,
};
use gpui_component::{
    input::{InputState as GpuiInputState, Input, InputEvent},
    text::TextView,
    Root,
};
use regex::Regex;
use theme::MonokaiTheme;

// Define actions for keyboard handling
actions!(omniemployee, [SendMessage, Backspace]);

/// Message role
#[derive(Debug, Clone, PartialEq)]
pub enum MessageRole {
    User,
    Assistant,
    System,
}

/// Chat message data
#[derive(Debug, Clone)]
pub struct ChatMessage {
    pub id: String,
    pub role: MessageRole,
    pub content: String,
    pub timestamp: String,
    pub tool_calls: Vec<ToolCall>,
}

impl ChatMessage {
    pub fn user(content: impl Into<String>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::User,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
        }
    }

    pub fn assistant(content: impl Into<String>, tool_calls: Vec<ToolCall>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::Assistant,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls,
        }
    }

    pub fn system(content: impl Into<String>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::System,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
        }
    }
}

/// Command types for /commands
#[derive(Debug, Clone)]
pub enum Command {
    Stats,
    Memory,
    Knowledge,
    Help,
    Clear,
    Reconnect,
    Config { key: String, value: String },
    Unknown(String),
}

impl Command {
    fn parse(input: &str) -> Option<Self> {
        let input = input.trim();
        if !input.starts_with('/') {
            return None;
        }

        let parts: Vec<&str> = input[1..].split_whitespace().collect();
        if parts.is_empty() {
            return None;
        }

        match parts[0].to_lowercase().as_str() {
            "stats" => Some(Command::Stats),
            "memory" => Some(Command::Memory),
            "knowledge" => Some(Command::Knowledge),
            "help" | "h" | "?" => Some(Command::Help),
            "clear" => Some(Command::Clear),
            "reconnect" => Some(Command::Reconnect),
            "config" if parts.len() >= 3 => Some(Command::Config {
                key: parts[1].to_string(),
                value: parts[2].to_string(),
            }),
            cmd => Some(Command::Unknown(cmd.to_string())),
        }
    }
}

/// App configuration
#[derive(Clone)]
pub struct AppConfig {
    pub show_memory: bool,
    pub show_knowledge: bool,
    pub show_tool_use: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            show_memory: true,
            show_knowledge: true,
            show_tool_use: true,
        }
    }
}

/// Connection status
#[derive(Debug, Clone, PartialEq)]
pub enum ConnectionStatus {
    Disconnected,
    Connecting,
    Connected,
    Error(String),
}

/// Live tool call being displayed (for real-time updates)
#[derive(Debug, Clone)]
pub struct LiveToolCall {
    pub id: String,
    pub name: String,
    pub arguments: serde_json::Value,
    pub result: Option<String>,
    pub status: ToolStatus,
    pub expanded: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ToolStatus {
    Running,
    Completed,
    Failed,
}


/// Main application state
pub struct App {
    theme: MonokaiTheme,
    messages: Vec<ChatMessage>,
    config: AppConfig,
    session_id: String,
    is_loading: bool,
    
    // Input component using gpui_component with full IME support
    input_state: Entity<GpuiInputState>,

    // API client
    api_client: ApiClient,
    connection_status: ConnectionStatus,

    // Agent info
    agent_model: String,
    agent_provider: String,
    agent_skills: Vec<String>,
    agent_tools: Vec<String>,

    // User management
    current_user_id: String,
    available_users: Vec<String>,
    show_user_dropdown: bool,

    // Collapsible panel states
    memory_expanded: bool,
    knowledge_expanded: bool,
    tool_expanded: bool,

    // Real data from API
    memory_items: Vec<MemoryItem>,
    knowledge_triples: Vec<KnowledgeTriple>,
    current_tool_calls: Vec<ToolCall>,
    
    // Live tool calls (real-time updates during streaming)
    live_tool_calls: Vec<LiveToolCall>,

    // Streaming state
    streaming_content: String,
    streaming_message_id: Option<String>,
}

impl App {
    fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let api_client = ApiClient::new(None);
        let session_id = uuid::Uuid::new_v4().to_string()[..8].to_string();

        // Create input state with gpui_component's InputState for proper IME support
        let input_state = cx.new(|cx| {
            GpuiInputState::new(window, cx)
                .placeholder("Type a message... (/ for commands)")
        });

        // Subscribe to input events for Enter key handling
        cx.subscribe_in(&input_state, window, |this, input_state, event: &InputEvent, window, cx| {
            match event {
                InputEvent::PressEnter { .. } => {
                    // Get text and clear input
                    let text = input_state.read(cx).value().to_string();
                    input_state.update(cx, |state, cx| {
                        state.set_value("", window, cx);
                    });
                    // Process message
                    this.send_message_with_text(text, cx);
                }
                _ => {}
            }
        }).detach();

        Self {
            theme: MonokaiTheme::new(),
            messages: vec![ChatMessage::system(
                "Connecting to OmniEmployee backend...",
            )],
            config: AppConfig::default(),
            session_id,
            is_loading: false,
            input_state,
            api_client,
            connection_status: ConnectionStatus::Connecting,
            agent_model: String::new(),
            agent_provider: String::new(),
            agent_skills: vec![],
            agent_tools: vec![],
            current_user_id: String::from("default"),
            available_users: vec![],
            show_user_dropdown: false,
            memory_expanded: false,
            knowledge_expanded: false,
            tool_expanded: true,
            memory_items: vec![],
            knowledge_triples: vec![],
            current_tool_calls: vec![],
            live_tool_calls: vec![],
            streaming_content: String::new(),
            streaming_message_id: None,
        }
    }

    fn initialize(&mut self, cx: &mut Context<Self>) {
        // Spawn background task to connect to API
        let api_client = self.api_client.clone();
        cx.spawn(async move |this, cx| {
            // Run blocking HTTP call in background thread pool
            let result = cx.background_spawn(async move {
                api_client.get_agent_info()
            }).await;

            match result {
                Ok(info) => {
                    let _ = this.update(cx, |app, cx| {
                        app.connection_status = ConnectionStatus::Connected;
                        app.agent_model = info.model;
                        app.agent_provider = info.provider;
                        app.agent_skills = info.skills;
                        app.agent_tools = info.tools;
                        app.config.show_memory = info.memory_enabled;
                        app.config.show_knowledge = info.knowledge_enabled;

                        app.messages.clear();
                        app.messages.push(ChatMessage::system(format!(
                            "Connected to OmniEmployee!\n\
                            Model: {} ({})\n\
                            Skills: {}\n\
                            Tools: {}\n\n\
                            Type a message or use /help for commands.",
                            app.agent_model,
                            app.agent_provider,
                            if app.agent_skills.is_empty() {
                                "none".to_string()
                            } else {
                                app.agent_skills.join(", ")
                            },
                            if app.agent_tools.is_empty() {
                                "none".to_string()
                            } else {
                                app.agent_tools.join(", ")
                            }
                        )));
                        cx.notify();
                    });
                }
                Err(e) => {
                    let _ = this.update(cx, |app, cx| {
                        app.connection_status =
                            ConnectionStatus::Error(format!("Failed to connect: {}", e));
                        app.messages.clear();
                        app.messages.push(ChatMessage::system(format!(
                            "⚠️ Could not connect to backend at {}.\n\n\
                            Make sure the server is running:\n\
                              uv run uvicorn src.omniemployee.web.app:app --port 8765\n\n\
                            Use /reconnect to try again.",
                            app.api_client.get_base_url()
                        )));
                        cx.notify();
                    });
                }
            }
        })
        .detach();

        // Load users list
        self.refresh_users(cx);

        // Load initial data
        self.refresh_sidebar_data(cx);
    }

    fn refresh_users(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move {
                api_client.get_users()
            }).await;
            if let Ok(response) = result {
                let _ = this.update(cx, |app, cx| {
                    app.available_users = response.users;
                    app.current_user_id = response.current;
                    cx.notify();
                });
            }
        })
        .detach();
    }

    fn switch_user(&mut self, user_id: String, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        let user_id_clone = user_id.clone();
        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move {
                api_client.switch_user(&user_id_clone)
            }).await;
            if let Ok(response) = result {
                if response.success {
                    let _ = this.update(cx, |app, cx| {
                        app.current_user_id = response.user_id;
                        app.show_user_dropdown = false;
                        // Generate new session_id for new user
                        app.session_id = uuid::Uuid::new_v4().to_string()[..8].to_string();
                        // Clear messages
                        app.messages.clear();
                        app.messages.push(ChatMessage::system(format!(
                            "Switched to user: {}\nNew session started.",
                            app.current_user_id
                        )));
                        // Refresh data for new user
                        app.refresh_sidebar_data(cx);
                        cx.notify();
                    });
                }
            }
        })
        .detach();
    }

    fn refresh_sidebar_data(&mut self, cx: &mut Context<Self>) {
        // Load memory items
        if self.config.show_memory {
            let api_client = self.api_client.clone();
            cx.spawn(async move |this, cx| {
                let result = cx.background_spawn(async move {
                    api_client.get_memory_context("", 20)
                }).await;
                if let Ok(response) = result {
                    let _ = this.update(cx, |app, cx| {
                        app.memory_items = response.items;
                        cx.notify();
                    });
                }
            })
            .detach();
        }

        // Load knowledge triples
        if self.config.show_knowledge {
            let api_client = self.api_client.clone();
            cx.spawn(async move |this, cx| {
                let result = cx.background_spawn(async move {
                    api_client.get_knowledge_triples(20)
                }).await;
                if let Ok(response) = result {
                    let _ = this.update(cx, |app, cx| {
                        app.knowledge_triples = response.triples;
                        cx.notify();
                    });
                }
            })
            .detach();
        }
    }

    fn send_message_with_text(&mut self, text: String, cx: &mut Context<Self>) {
        let text = text.trim().to_string();
        
        if text.is_empty() || self.is_loading {
            return;
        }

        // Check for command
        if let Some(command) = Command::parse(&text) {
            self.handle_command(command, cx);
            return;
        }

        // Add user message
        self.messages.push(ChatMessage::user(&text));
        self.is_loading = true;
        self.current_tool_calls.clear();
        self.live_tool_calls.clear();  // Clear live tool calls for new message
        
        // Create streaming assistant message placeholder
        let stream_msg_id = uuid::Uuid::new_v4().to_string();
        self.streaming_message_id = Some(stream_msg_id.clone());
        self.streaming_content.clear();
        self.messages.push(ChatMessage {
            id: stream_msg_id.clone(),
            role: MessageRole::Assistant,
            content: String::new(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
        });
        cx.notify();

        // Send to API with streaming
        let api_client = self.api_client.clone();
        let session_id = self.session_id.clone();
        let message = text.clone();

        // Use channel to send streaming updates
        let (tx, rx) = std::sync::mpsc::channel::<StreamEvent>();

        // Spawn background task for streaming
        cx.spawn(async move |this, cx| {
            // Start streaming in background
            let tx_clone = tx.clone();
            let stream_result = cx.background_spawn(async move {
                api_client.chat_stream(&message, Some(session_id), |event| {
                    let _ = tx_clone.send(event);
                })
            });

            // Process streaming events
            loop {
                match rx.try_recv() {
                    Ok(event) => {
                        match event {
                            StreamEvent::Chunk { content } => {
                                let _ = this.update(cx, |app, cx| {
                                    app.streaming_content.push_str(&content);
                                    // Update the last message content
                                    if let Some(msg) = app.messages.last_mut() {
                                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                                            msg.content = app.streaming_content.clone();
                                        }
                                    }
                                    cx.notify();
                                });
                            }
                            StreamEvent::ToolStart { name, arguments, id } => {
                                // Tool call started - add to live tool calls immediately
                                let _ = this.update(cx, |app, cx| {
                                    // Check if we already have this tool call
                                    if !app.live_tool_calls.iter().any(|tc| tc.id == id) {
                                        app.live_tool_calls.push(LiveToolCall {
                                            id,
                                            name,
                                            arguments,
                                            result: None,
                                            status: ToolStatus::Running,
                                            expanded: true,  // Auto-expand new tool calls
                                        });
                                        app.tool_expanded = true;  // Make sure panel is visible
                                    }
                                    cx.notify();
                                });
                            }
                            StreamEvent::ToolResult { id, result } => {
                                // Tool call completed - update the result
                                let _ = this.update(cx, |app, cx| {
                                    if let Some(tc) = app.live_tool_calls.iter_mut().find(|tc| tc.id == id) {
                                        tc.result = Some(result);
                                        tc.status = ToolStatus::Completed;
                                    }
                                    cx.notify();
                                });
                            }
                            StreamEvent::Done { tool_calls } => {
                                let _ = this.update(cx, |app, cx| {
                                    // Convert tool calls
                                    let tcs: Vec<ToolCall> = tool_calls
                                        .into_iter()
                                        .map(|tc| ToolCall {
                                            name: tc.name,
                                            arguments: tc.arguments,
                                            result: None,
                                            success: true,
                                        })
                                        .collect();
                                    
                                    app.current_tool_calls = tcs.clone();
                                    
                                    // Mark all live tool calls as completed
                                    for tc in &mut app.live_tool_calls {
                                        if tc.status == ToolStatus::Running {
                                            tc.status = ToolStatus::Completed;
                                        }
                                    }
                                    
                                    // Update tool calls in message
                                    if let Some(msg) = app.messages.last_mut() {
                                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                                            msg.tool_calls = tcs;
                                        }
                                    }
                                    
                                    app.is_loading = false;
                                    app.streaming_message_id = None;
                                    app.refresh_sidebar_data(cx);
                                    cx.notify();
                                });
                                break;
                            }
                            StreamEvent::Error { content } => {
                                let _ = this.update(cx, |app, cx| {
                                    if let Some(msg) = app.messages.last_mut() {
                                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                                            msg.content = format!("⚠️ Error: {}", content);
                                            msg.role = MessageRole::System;
                                        }
                                    }
                                    // Mark all live tool calls as failed
                                    for tc in &mut app.live_tool_calls {
                                        if tc.status == ToolStatus::Running {
                                            tc.status = ToolStatus::Failed;
                                        }
                                    }
                                    app.is_loading = false;
                                    app.streaming_message_id = None;
                                    cx.notify();
                                });
                                break;
                            }
                        }
                    }
                    Err(std::sync::mpsc::TryRecvError::Empty) => {
                        // No message yet, wait a bit
                        smol::Timer::after(std::time::Duration::from_millis(10)).await;
                    }
                    Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                        // Channel closed, check if stream finished
                        break;
                    }
                }
            }

            // Wait for background task to finish and handle errors
            match stream_result.await {
                Ok(_) => {}
                Err(e) => {
                    let _ = this.update(cx, |app, cx| {
                        if app.is_loading {
                            app.messages.push(ChatMessage::system(format!(
                                "⚠️ Error: {}. Is the backend running?",
                                e
                            )));
                            app.is_loading = false;
                            app.streaming_message_id = None;
                        }
                        cx.notify();
                    });
                }
            }
        })
        .detach();
    }

    fn handle_send_click(
        &mut self,
        _event: &ClickEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        // Get text and clear input
        let text = self.input_state.read(cx).value().to_string();
        self.input_state.update(cx, |state, cx| {
            state.set_value("", window, cx);
        });
        self.send_message_with_text(text, cx);
    }

    fn handle_command(&mut self, command: Command, cx: &mut Context<Self>) {
        match command {
            Command::Help => {
                self.messages.push(ChatMessage::system(
                    "**Available Commands:**\n\n\
                    /stats - Show agent statistics\n\
                    /memory - Show memory statistics\n\
                    /knowledge - Show learned knowledge\n\
                    /clear - Clear conversation\n\
                    /reconnect - Reconnect to backend\n\
                    /config <key> <value> - Update config\n\n\
                    Config keys: show_memory, show_knowledge, show_tools",
                ));
            }
            Command::Stats => {
                let api_client = self.api_client.clone();
                self.messages
                    .push(ChatMessage::system("Fetching stats..."));
                cx.notify();

                cx.spawn(async move |this, cx| {
                    let result = cx.background_spawn(async move {
                        api_client.get_agent_info()
                    }).await;

                    let mut stats_text = String::from("📊 **Agent Statistics**\n\n");
                    if let Ok(info) = result {
                        stats_text.push_str(&format!("Model: {}\n", info.model));
                        stats_text.push_str(&format!("Provider: {}\n", info.provider));
                        stats_text.push_str(&format!("Skills: {}\n", info.skills.join(", ")));
                        stats_text.push_str(&format!("Tools: {}\n", info.tools.join(", ")));
                        stats_text.push_str(&format!(
                            "Memory: {}\n",
                            if info.memory_enabled {
                                "enabled"
                            } else {
                                "disabled"
                            }
                        ));
                        stats_text.push_str(&format!(
                            "Knowledge: {}",
                            if info.knowledge_enabled {
                                "enabled"
                            } else {
                                "disabled"
                            }
                        ));
                    } else {
                        stats_text.push_str("Failed to fetch agent info");
                    }

                    let _ = this.update(cx, |app, cx| {
                        app.messages.pop();
                        app.messages.push(ChatMessage::system(stats_text));
                        cx.notify();
                    });
                })
                .detach();
            }
            Command::Memory => {
                let api_client = self.api_client.clone();
                self.messages
                    .push(ChatMessage::system("Fetching memory stats..."));
                cx.notify();

                cx.spawn(async move |this, cx| {
                    let result = cx.background_spawn(async move {
                        api_client.get_memory_stats()
                    }).await;

                    let mut mem_text = String::from("🧠 **Memory Statistics**\n\n");
                    if let Ok(stats) = result {
                        mem_text.push_str(&format!("L1 Working: {} nodes\n", stats.l1_count));
                        mem_text.push_str(&format!("L2 Vector: {} nodes\n", stats.l2_vector_count));
                        mem_text.push_str(&format!(
                            "L2 Graph: {} nodes, {} edges\n",
                            stats.l2_graph_nodes, stats.l2_graph_edges
                        ));
                        mem_text.push_str(&format!("L3 Facts: {}\n", stats.l3_facts));
                        mem_text.push_str(&format!("L3 Links: {}", stats.l3_links));
                    } else {
                        mem_text.push_str("Memory system not available");
                    }

                    let _ = this.update(cx, |app, cx| {
                        app.messages.pop();
                        app.messages.push(ChatMessage::system(mem_text));
                        cx.notify();
                    });
                })
                .detach();
            }
            Command::Knowledge => {
                let api_client = self.api_client.clone();
                self.messages
                    .push(ChatMessage::system("Fetching knowledge stats..."));
                cx.notify();

                cx.spawn(async move |this, cx| {
                    let result = cx.background_spawn(async move {
                        api_client.get_knowledge_stats()
                    }).await;

                    let mut know_text = String::from("📚 **Knowledge Statistics**\n\n");
                    if let Ok(stats) = result {
                        if stats.status.as_deref() == Some("unavailable") {
                            know_text.push_str("Knowledge system not available");
                        } else {
                            know_text.push_str(&format!("Total triples: {}\n", stats.total_triples));
                            know_text
                                .push_str(&format!("Unique subjects: {}\n", stats.unique_subjects));
                            know_text.push_str(&format!(
                                "Unique predicates: {}\n",
                                stats.unique_predicates
                            ));
                            know_text
                                .push_str(&format!("Total updates: {}\n", stats.total_updates));
                            know_text.push_str(&format!(
                                "Pending confirmations: {}",
                                stats.pending_confirmations
                            ));
                        }
                    } else {
                        know_text.push_str("Knowledge system not available");
                    }

                    let _ = this.update(cx, |app, cx| {
                        app.messages.pop();
                        app.messages.push(ChatMessage::system(know_text));
                        cx.notify();
                    });
                })
                .detach();
            }
            Command::Clear => {
                let api_client = self.api_client.clone();
                let session_id = self.session_id.clone();

                cx.spawn(async move |this, cx| {
                    let _ = cx.background_spawn(async move {
                        api_client.clear_chat(Some(session_id))
                    }).await;

                    let _ = this.update(cx, |app, cx| {
                        app.messages.clear();
                        app.messages
                            .push(ChatMessage::system("Conversation cleared."));
                        app.current_tool_calls.clear();
                        cx.notify();
                    });
                })
                .detach();
            }
            Command::Reconnect => {
                self.messages.clear();
                self.messages
                    .push(ChatMessage::system("Reconnecting..."));
                self.connection_status = ConnectionStatus::Connecting;
                cx.notify();
                self.initialize(cx);
            }
            Command::Config { key, value } => {
                let response = match key.as_str() {
                    "show_memory" => {
                        self.config.show_memory = value.to_lowercase() == "true";
                        format!("✓ show_memory set to {}", self.config.show_memory)
                    }
                    "show_knowledge" => {
                        self.config.show_knowledge = value.to_lowercase() == "true";
                        format!("✓ show_knowledge set to {}", self.config.show_knowledge)
                    }
                    "show_tools" => {
                        self.config.show_tool_use = value.to_lowercase() == "true";
                        format!("✓ show_tools set to {}", self.config.show_tool_use)
                    }
                    _ => format!("Unknown config key: {}", key),
                };
                self.messages.push(ChatMessage::system(response));
            }
            Command::Unknown(cmd) => {
                self.messages.push(ChatMessage::system(format!(
                    "Unknown command: /{}. Type /help for help.",
                    cmd
                )));
            }
        }
        cx.notify();
    }

    fn toggle_memory(&mut self, _: &ClickEvent, _window: &mut Window, cx: &mut Context<Self>) {
        self.memory_expanded = !self.memory_expanded;
        cx.notify();
    }

    fn toggle_knowledge(&mut self, _: &ClickEvent, _window: &mut Window, cx: &mut Context<Self>) {
        self.knowledge_expanded = !self.knowledge_expanded;
        cx.notify();
    }

    fn toggle_tools(&mut self, _: &ClickEvent, _window: &mut Window, cx: &mut Context<Self>) {
        self.tool_expanded = !self.tool_expanded;
        cx.notify();
    }

    fn toggle_tool_call(&mut self, tool_id: String, _window: &mut Window, cx: &mut Context<Self>) {
        if let Some(tc) = self.live_tool_calls.iter_mut().find(|t| t.id == tool_id) {
            tc.expanded = !tc.expanded;
            cx.notify();
        }
    }

    /// Filter out tool call patterns from LLM response to keep it clean
    fn clean_response_content(content: &str) -> String {
        let mut result = content.to_string();
        
        // Remove tool output blocks - entire sections starting with tool emoji
        // Pattern: 🔧 **tool_name** followed by content until next section or end
        let tool_block_patterns = [
            // Full tool output block: 🔧 **name**\n_desc_\n```...```
            r"(?s)🔧\s*\*\*\w+\*\*.*?```[\s\S]*?```",
            // Tool header with description: 🔧 **name**\n_desc..._
            r"🔧\s*\*\*\w+\*\*\s*\n_[^_]*\.\.\._",
            // Just tool header: 🔧 **name**
            r"🔧\s*\*\*\w+\*\*",
            // Summarized marker: [Summarized from N chars]
            r"\[Summarized from \d+ chars\]",
            // Standalone descriptions: _text..._
            r"_[^_\n]+\.\.\._",
        ];
        
        for pattern in tool_block_patterns {
            if let Ok(re) = Regex::new(pattern) {
                result = re.replace_all(&result, "").to_string();
            }
        }
        
        // Remove code blocks that are just tool output markers
        if let Ok(re) = Regex::new(r"```\s*\n?\s*```") {
            result = re.replace_all(&result, "").to_string();
        }
        
        // Remove multiple consecutive newlines
        while result.contains("\n\n\n") {
            result = result.replace("\n\n\n", "\n\n");
        }
        
        result.trim().to_string()
    }

    fn render_header(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;

        let status_color = match &self.connection_status {
            ConnectionStatus::Connected => theme.accent_green,
            ConnectionStatus::Connecting => theme.accent_yellow,
            ConnectionStatus::Disconnected => theme.foreground_muted,
            ConnectionStatus::Error(_) => theme.accent_red,
        };

        let status_text = match &self.connection_status {
            ConnectionStatus::Connected => "Connected",
            ConnectionStatus::Connecting => "Connecting...",
            ConnectionStatus::Disconnected => "Disconnected",
            ConnectionStatus::Error(_) => "Error",
        };

        div()
            .w_full()
            .px_4()
            .py_3()
            .bg(theme.background_secondary)
            .border_b_1()
            .border_color(theme.border)
            .flex()
            .items_center()
            .justify_between()
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_3()
                    .child(div().text_xl().child("🤖"))
                    .child(
                        div()
                            .child(
                                div()
                                    .text_lg()
                                    .font_weight(FontWeight::BOLD)
                                    .text_color(theme.accent_cyan)
                                    .child("OmniEmployee"),
                            )
                            .child(
                                div()
                                    .text_xs()
                                    .text_color(theme.foreground_muted)
                                    .child(if self.agent_model.is_empty() {
                                        "AI Assistant".to_string()
                                    } else {
                                        format!("{} • {}", self.agent_model, self.agent_provider)
                                    }),
                            ),
                    ),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_4()
                    .child(self.render_user_selector(cx))
                    .child(self.render_status_indicator(status_text, status_color))
                    .child(self.render_status_dot("Memory", self.config.show_memory))
                    .child(self.render_status_dot("Knowledge", self.config.show_knowledge)),
            )
    }

    fn render_user_selector(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;
        let current_user = self.current_user_id.clone();
        let show_dropdown = self.show_user_dropdown;
        let users = self.available_users.clone();

        div()
            .id("user-selector")
            .child(
                // User button
                div()
                    .id("user-button")
                    .px_3()
                    .py_1()
                    .rounded(px(6.))
                    .bg(theme.background)
                    .border_1()
                    .border_color(theme.border)
                    .cursor_pointer()
                    .flex()
                    .items_center()
                    .gap_2()
                    .hover(|s| s.bg(theme.background_elevated))
                    .on_click(cx.listener(|this, _event, _window, cx| {
                        this.show_user_dropdown = !this.show_user_dropdown;
                        cx.notify();
                    }))
                    .child(
                        div()
                            .text_xs()
                            .text_color(theme.foreground_muted)
                            .child("👤"),
                    )
                    .child(
                        div()
                            .text_sm()
                            .text_color(theme.foreground)
                            .child(SharedString::from(current_user)),
                    )
                    .child(
                        div()
                            .text_xs()
                            .text_color(theme.foreground_muted)
                            .child(if show_dropdown { "▲" } else { "▼" }),
                    ),
            )
            .when(show_dropdown, |this| {
                // Use deferred + anchored to render dropdown on top layer
                this.child(
                    deferred(
                        anchored().child(
                            // Dropdown menu - rendered on top of everything
                            div()
                                .id("user-dropdown-menu")
                                .occlude()
                                .w(px(200.))
                                .bg(theme.background_elevated)
                                .border_1()
                                .border_color(theme.border)
                                .rounded(px(6.))
                                .shadow_lg()
                                .flex()
                                .flex_col()
                                // User items
                                .children(
                                    users.into_iter().map(|user| {
                                        let user_clone = user.clone();
                                        let is_current = user == self.current_user_id;
                                        div()
                                            .id(SharedString::from(format!("user-{}", user)))
                                            .w_full()
                                            .px_3()
                                            .py_2()
                                            .cursor_pointer()
                                            .text_sm()
                                            .text_color(if is_current { theme.accent_cyan } else { theme.foreground })
                                            .bg(if is_current { theme.background_highlight } else { theme.background_elevated })
                                            .hover(|s| s.bg(theme.background_highlight))
                                            .on_click(cx.listener(move |this, _event, _window, cx| {
                                                this.switch_user(user_clone.clone(), cx);
                                            }))
                                            .child(SharedString::from(user))
                                    })
                                )
                                // Divider
                                .child(
                                    div()
                                        .h(px(1.))
                                        .w_full()
                                        .bg(theme.border)
                                )
                                // New user option
                                .child(
                                    div()
                                        .id("new-user-option")
                                        .w_full()
                                        .px_3()
                                        .py_2()
                                        .cursor_pointer()
                                        .text_sm()
                                        .text_color(theme.accent_green)
                                        .hover(|s| s.bg(theme.background_highlight))
                                        .on_click(cx.listener(|this, _event, _window, cx| {
                                            this.handle_create_new_user(cx);
                                        }))
                                        .child("+ New User..."),
                                ),
                        ),
                    ),
                )
            })
    }

    fn handle_create_new_user(&mut self, cx: &mut Context<Self>) {
        // For now, create a new user with a UUID-based name
        // A proper implementation would show a dialog
        let new_user_id = format!("user_{}", &uuid::Uuid::new_v4().to_string()[..8]);
        let api_client = self.api_client.clone();
        let user_id = new_user_id.clone();
        
        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move {
                api_client.create_user(&user_id)
            }).await;
            if let Ok(response) = result {
                if response.success {
                    let _ = this.update(cx, |app, cx| {
                        app.current_user_id = response.user_id.clone();
                        app.show_user_dropdown = false;
                        if !app.available_users.contains(&response.user_id) {
                            app.available_users.push(response.user_id.clone());
                        }
                        // Generate new session
                        app.session_id = uuid::Uuid::new_v4().to_string()[..8].to_string();
                        app.messages.clear();
                        app.messages.push(ChatMessage::system(format!(
                            "Created and switched to new user: {}\nNew session started.",
                            response.user_id
                        )));
                        app.refresh_sidebar_data(cx);
                        cx.notify();
                    });
                }
            }
        })
        .detach();
    }

    fn render_status_indicator(&self, label: &'static str, color: Hsla) -> impl IntoElement {
        let theme = &self.theme;

        div()
            .flex()
            .items_center()
            .gap_1()
            .child(
                div()
                    .w_2()
                    .h_2()
                    .rounded_full()
                    .bg(color)
                    .when(
                        self.connection_status == ConnectionStatus::Connecting,
                        |el| el.bg(color.opacity(0.6)),
                    ),
            )
            .child(div().text_xs().text_color(theme.foreground_dim).child(label))
    }

    fn render_status_dot(&self, label: &'static str, active: bool) -> impl IntoElement {
        let theme = &self.theme;

        div()
            .flex()
            .items_center()
            .gap_1()
            .child(
                div()
                    .w_2()
                    .h_2()
                    .rounded_full()
                    .bg(if active {
                        theme.accent_green
                    } else {
                        theme.foreground_muted
                    }),
            )
            .child(div().text_xs().text_color(theme.foreground_dim).child(label))
    }

    fn render_messages(&self) -> impl IntoElement {
        let theme = &self.theme;

        // Pre-render all message elements with markdown support
        let message_elements: Vec<_> = self.messages.iter().enumerate().map(|(idx, msg)| {
            let (bg_color, align_end, role_label, role_color) = match msg.role {
                MessageRole::User => (theme.user_message_bg, true, "You", theme.accent_green),
                MessageRole::Assistant => {
                    (theme.assistant_message_bg, false, "Assistant", theme.accent_cyan)
                }
                MessageRole::System => {
                    (theme.system_message_bg, false, "System", theme.accent_yellow)
                }
            };

            let has_tools = !msg.tool_calls.is_empty();
            let cleaned_content = Self::clean_response_content(&msg.content);
            
            // Use TextView::markdown for rendering markdown content
            let content_view = TextView::markdown(
                SharedString::from(format!("msg-{}", idx)),
                cleaned_content,
            );

            div()
                .w_full()
                .flex()
                .flex_col()
                .mb_3()
                .child(
                    div()
                        .w_full()
                        .flex()
                        .when(align_end, |el| el.justify_end())
                        .when(!align_end, |el| el.justify_start())
                        .child(
                            div()
                                .max_w(px(600.))
                                .p_3()
                                .rounded_lg()
                                .bg(bg_color)
                                .child(
                                    div()
                                        .flex()
                                        .justify_between()
                                        .mb_1()
                                        .child(
                                            div()
                                                .text_sm()
                                                .font_weight(FontWeight::SEMIBOLD)
                                                .text_color(role_color)
                                                .child(role_label),
                                        )
                                        .child(
                                            div()
                                                .text_xs()
                                                .text_color(theme.foreground_muted)
                                                .child(msg.timestamp.clone()),
                                        ),
                                )
                                .child(
                                    div()
                                        .text_sm()
                                        .child(content_view),
                                )
                                .when(has_tools, |el| {
                                    el.child(
                                        div()
                                            .mt_2()
                                            .pt_2()
                                            .border_t_1()
                                            .border_color(theme.border)
                                            .child(
                                                div()
                                                    .text_xs()
                                                    .text_color(theme.accent_orange)
                                                    .font_weight(FontWeight::MEDIUM)
                                                    .child(format!(
                                                        "🔧 {} tool(s) used",
                                                        msg.tool_calls.len()
                                                    )),
                                            )
                                            .children(msg.tool_calls.iter().map(|tc| {
                                                div()
                                                    .text_xs()
                                                    .text_color(theme.foreground_dim)
                                                    .child(format!("• {}", tc.name))
                                            })),
                                    )
                                }),
                        ),
                )
        }).collect();

        div()
            .id("messages-container")
            .flex_1()
            .overflow_y_scroll()
            .bg(theme.background)
            .p_4()
            .children(message_elements)
            .when(self.is_loading, |el| {
                el.child(
                    div()
                        .w_full()
                        .flex()
                        .justify_start()
                        .child(
                            div()
                                .p_3()
                                .rounded_lg()
                                .bg(theme.assistant_message_bg)
                                .child(
                                    div()
                                        .text_sm()
                                        .text_color(theme.foreground_muted)
                                        .child("Thinking..."),
                                ),
                        ),
                )
            })
    }

    fn render_collapsible_panel(
        &self,
        id: &'static str,
        icon: &'static str,
        title: &'static str,
        expanded: bool,
        color: Hsla,
        items: Vec<(String, String)>,
        cx: &Context<Self>,
    ) -> impl IntoElement {
        let theme = &self.theme;
        let content_id = format!("{}-content", id);

        let click_handler: Box<dyn Fn(&mut Self, &ClickEvent, &mut Window, &mut Context<Self>)> =
            match id {
                "tools" => Box::new(Self::toggle_tools),
                "memory" => Box::new(Self::toggle_memory),
                "knowledge" => Box::new(Self::toggle_knowledge),
                _ => Box::new(|_, _, _, _| {}),
            };

        div()
            .w_full()
            .rounded_lg()
            .overflow_hidden()
            .border_1()
            .border_color(theme.border)
            .mb_2()
            .child(
                div()
                    .id(SharedString::from(id.to_string()))
                    .cursor_pointer()
                    .flex()
                    .items_center()
                    .justify_between()
                    .w_full()
                    .px_3()
                    .py_2()
                    .bg(theme.background_elevated)
                    .hover(|style| style.bg(theme.background_highlight))
                    .on_click(cx.listener(move |this, event, window, cx| {
                        click_handler(this, event, window, cx)
                    }))
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .gap_2()
                            .child(
                                div()
                                    .text_xs()
                                    .text_color(theme.foreground_muted)
                                    .child(if expanded { "▼" } else { "▶" }),
                            )
                            .child(div().text_sm().child(icon))
                            .child(
                                div()
                                    .text_sm()
                                    .font_weight(FontWeight::MEDIUM)
                                    .text_color(color)
                                    .child(title),
                            ),
                    )
                    .child(
                        div()
                            .px_2()
                            .py_px()
                            .rounded_full()
                            .bg(color.opacity(0.2))
                            .text_xs()
                            .text_color(color)
                            .child(items.len().to_string()),
                    ),
            )
            .when(expanded, |el| {
                el.child(
                    div()
                        .id(SharedString::from(content_id))
                        .w_full()
                        .max_h(px(200.))
                        .overflow_y_scroll()
                        .bg(theme.background_secondary)
                        .when(items.is_empty(), |el| {
                            el.child(
                                div()
                                    .w_full()
                                    .px_3()
                                    .py_2()
                                    .text_sm()
                                    .text_color(theme.foreground_muted)
                                    .child("No items"),
                            )
                        })
                        .children(items.iter().enumerate().map(|(i, (primary, secondary))| {
                            let is_last = i == items.len() - 1;
                            div()
                                .w_full()
                                .px_3()
                                .py_2()
                                .when(!is_last, |el| {
                                    el.border_b_1().border_color(theme.border)
                                })
                                .child(
                                    div()
                                        .text_sm()
                                        .text_color(theme.foreground)
                                        .overflow_hidden()
                                        .child(primary.clone()),
                                )
                                .child(
                                    div()
                                        .text_xs()
                                        .text_color(theme.foreground_dim)
                                        .child(secondary.clone()),
                                )
                        })),
                )
            })
    }

    fn render_live_tool_panel(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;
        let has_tools = !self.live_tool_calls.is_empty();

        div()
            .w_full()
            .rounded_lg()
            .overflow_hidden()
            .border_1()
            .border_color(theme.border)
            .mb_2()
            .child(
                div()
                    .id("tools-header")
                    .cursor_pointer()
                    .flex()
                    .items_center()
                    .justify_between()
                    .w_full()
                    .px_3()
                    .py_2()
                    .bg(theme.background_elevated)
                    .hover(|style| style.bg(theme.background_highlight))
                    .on_click(cx.listener(Self::toggle_tools))
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .gap_2()
                            .child(
                                div()
                                    .text_xs()
                                    .text_color(theme.foreground_muted)
                                    .child(if self.tool_expanded { "▼" } else { "▶" }),
                            )
                            .child(div().text_sm().child("🔧"))
                            .child(
                                div()
                                    .text_sm()
                                    .font_weight(FontWeight::MEDIUM)
                                    .text_color(theme.accent_orange)
                                    .child("Tool Use"),
                            ),
                    )
                    .child(
                        div()
                            .px_2()
                            .py_px()
                            .rounded_full()
                            .bg(theme.accent_orange.opacity(0.2))
                            .text_xs()
                            .text_color(theme.accent_orange)
                            .child(self.live_tool_calls.len().to_string()),
                    ),
            )
            .when(self.tool_expanded, |el| {
                let content = div()
                    .id("live-tools-content")
                    .w_full()
                    .max_h(px(400.))
                    .overflow_y_scroll()
                    .bg(theme.background_secondary)
                    .when(!has_tools, |inner| {
                        inner.child(
                            div()
                                .w_full()
                                .px_3()
                                .py_2()
                                .text_sm()
                                .text_color(theme.foreground_muted)
                                .child("No tool calls yet"),
                        )
                    })
                    .children(self.live_tool_calls.iter().enumerate().map(|(i, tc)| {
                        let is_last = i == self.live_tool_calls.len() - 1;
                        let status_icon = match tc.status {
                            ToolStatus::Running => "⏳",
                            ToolStatus::Completed => "✅",
                            ToolStatus::Failed => "❌",
                        };
                        let status_color = match tc.status {
                            ToolStatus::Running => theme.accent_yellow,
                            ToolStatus::Completed => theme.accent_green,
                            ToolStatus::Failed => theme.accent_red,
                        };
                        
                        // Get result content (show result by default, not arguments)
                        let result_content = tc.result.clone().unwrap_or_else(|| {
                            if tc.status == ToolStatus::Running {
                                "Running...".to_string()
                            } else {
                                "No result".to_string()
                            }
                        });
                        
                        let tool_id = tc.id.clone();

                        div()
                            .w_full()
                            .when(!is_last, |inner| {
                                inner.border_b_1().border_color(theme.border)
                            })
                            .child(
                                div()
                                    .id(SharedString::from(format!("tool-{}", tc.id)))
                                    .w_full()
                                    .px_3()
                                    .py_2()
                                    .cursor_pointer()
                                    .hover(|style| style.bg(theme.background_highlight))
                                    .on_click(cx.listener(move |this, _event, window, cx| {
                                        this.toggle_tool_call(tool_id.clone(), window, cx);
                                    }))
                                    .child(
                                        div()
                                            .flex()
                                            .items_center()
                                            .gap_2()
                                            .child(
                                                div()
                                                    .text_xs()
                                                    .text_color(theme.foreground_muted)
                                                    .child(if tc.expanded { "▼" } else { "▶" }),
                                            )
                                            .child(div().text_xs().child(status_icon))
                                            .child(
                                                div()
                                                    .text_sm()
                                                    .font_weight(FontWeight::MEDIUM)
                                                    .text_color(status_color)
                                                    .child(tc.name.clone()),
                                            ),
                                    )
                                    .when(tc.expanded, |inner| {
                                        // Use markdown rendering for tool results
                                        let result_view = TextView::markdown(
                                            SharedString::from(format!("tool-result-{}", tc.id)),
                                            result_content.clone(),
                                        );
                                        let result_container_id = format!("tool-result-container-{}", tc.id);
                                        
                                        inner.child(
                                            div()
                                                .id(SharedString::from(result_container_id))
                                                .mt_2()
                                                .p_2()
                                                .rounded(px(4.))
                                                .bg(theme.background)
                                                .max_h(px(300.))
                                                .overflow_y_scroll()
                                                // Show result with markdown rendering
                                                .child(
                                                    div()
                                                        .text_xs()
                                                        .text_color(theme.foreground_muted)
                                                        .font_weight(FontWeight::MEDIUM)
                                                        .mb_1()
                                                        .child("Result:"),
                                                )
                                                .child(
                                                    div()
                                                        .text_xs()
                                                        .child(result_view),
                                                ),
                                        )
                                    }),
                            )
                    }));
                el.child(content)
            })
    }

    fn render_sidebar(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;

        // Prepare memory items (use chars().take() for safe UTF-8 truncation)
        let memory_items: Vec<(String, String)> = self
            .memory_items
            .iter()
            .map(|m| {
                let content_preview = if m.content.chars().count() > 50 {
                    let preview: String = m.content.chars().take(50).collect();
                    format!("{}...", preview)
                } else {
                    m.content.clone()
                };
                (content_preview, format!("E={:.2} • {}", m.energy, m.tier))
            })
            .collect();

        // Prepare knowledge items
        let knowledge_items: Vec<(String, String)> = self
            .knowledge_triples
            .iter()
            .map(|k| {
                (
                    format!("({}, {}, {})", k.subject, k.predicate, k.object),
                    format!("conf={:.2} • {}", k.confidence, k.source),
                )
            })
            .collect();

        div()
            .w(px(300.))
            .h_full()
            .bg(theme.background_secondary)
            .border_l_1()
            .border_color(theme.border)
            .flex()
            .flex_col()
            .child(
                div()
                    .px_4()
                    .py_3()
                    .border_b_1()
                    .border_color(theme.border)
                    .child(
                        div()
                            .text_sm()
                            .font_weight(FontWeight::SEMIBOLD)
                            .text_color(theme.foreground)
                            .child("Context"),
                    )
                    .child(
                        div()
                            .text_xs()
                            .text_color(theme.foreground_muted)
                            .child("Memory, Knowledge & Tools"),
                    ),
            )
            .child(
                div()
                    .id("sidebar-panels")
                    .flex_1()
                    .overflow_y_scroll()
                    .p_3()
                    // Tool Use Panel with live updates
                    .when(self.config.show_tool_use, |el| {
                        el.child(self.render_live_tool_panel(cx))
                    })
                    // Memory Panel
                    .when(self.config.show_memory, |el| {
                        el.child(self.render_collapsible_panel(
                            "memory",
                            "🧠",
                            "Memory",
                            self.memory_expanded,
                            theme.accent_purple,
                            memory_items,
                            cx,
                        ))
                    })
                    // Knowledge Panel
                    .when(self.config.show_knowledge, |el| {
                        el.child(self.render_collapsible_panel(
                            "knowledge",
                            "📚",
                            "Knowledge",
                            self.knowledge_expanded,
                            theme.accent_green,
                            knowledge_items,
                            cx,
                        ))
                    }),
            )
    }

    fn render_input(&self, _window: &Window, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;
        let is_loading = self.is_loading;
        let is_connected = self.connection_status == ConnectionStatus::Connected;

        div()
            .w_full()
            .p_3()
            .bg(theme.background_secondary)
            .border_t_1()
            .border_color(theme.border)
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_2()
                    .child(
                        // Use gpui_component Input with proper IME support
                        div()
                            .flex_1()
                            .child(
                                Input::new(&self.input_state)
                                    .appearance(false) // Remove default styling
                            ),
                    )
                    .child(
                        div()
                            .id("send-btn")
                            .cursor_pointer()
                            .px_4()
                            .py_2()
                            .rounded_lg()
                            .bg(if is_loading || !is_connected {
                                theme.foreground_muted
                            } else {
                                theme.accent_cyan
                            })
                            .text_sm()
                            .font_weight(FontWeight::MEDIUM)
                            .text_color(theme.background)
                            .when(is_connected && !is_loading, |el| {
                                el.hover(|style| style.bg(theme.accent_cyan.opacity(0.8)))
                            })
                            .on_click(cx.listener(Self::handle_send_click))
                            .child(if is_loading { "..." } else { "Send" }),
                    ),
            )
            .child(
                div()
                    .mt_1()
                    .text_xs()
                    .text_color(theme.foreground_muted)
                    .child("Tip: /stats, /memory, /knowledge, /help, /reconnect"),
            )
    }
}

impl Render for App {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let theme = &self.theme;

        div()
            .size_full()
            .bg(theme.background)
            .text_color(theme.foreground)
            .flex()
            .child(
                div()
                    .flex_1()
                    .flex()
                    .flex_col()
                    .child(self.render_header(cx))
                    .child(self.render_messages())
                    .child(self.render_input(window, cx)),
            )
            .child(self.render_sidebar(cx))
    }
}

fn main() {
    Application::new().run(|cx| {
        // Initialize gpui-component (required before using any component)
        gpui_component::init(cx);

        let window_options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                None,
                size(px(1200.), px(800.)),
                cx,
            ))),
            titlebar: Some(TitlebarOptions {
                title: Some(SharedString::from("OmniEmployee")),
                ..Default::default()
            }),
            ..Default::default()
        };

        cx.open_window(window_options, |window, cx| {
            // Create app with window reference for input component initialization
            let app_entity = cx.new(|cx| App::new(window, cx));

            // Initialize the app after creation (connect to backend)
            app_entity.update(cx, |app, cx| {
                app.initialize(cx);
            });

            // Focus the input after initialization
            app_entity.update(cx, |app, cx| {
                app.input_state.update(cx, |state, cx| {
                    state.focus(window, cx);
                });
            });

            // Wrap in Root for gpui-component theming support
            cx.new(|cx| Root::new(app_entity.clone(), window, cx))
        })
        .unwrap();
    });
}
