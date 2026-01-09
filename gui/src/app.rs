//! Core App state and initialization for OmniEmployee GUI

use gpui::{div, AppContext as _, Context, Entity, IntoElement, ParentElement, Render, Styled, Window};
use gpui_component::input::{InputEvent, InputState as GpuiInputState};

use crate::api::{ApiClient, ContextKnowledge, ContextMemory, KnowledgeTriple, MemoryItem, ToolCall};
use crate::models::{AppConfig, ChatMessage, ConnectionStatus, LiveToolCall};
use crate::theme::MonokaiTheme;

/// Main application state
pub struct App {
    pub theme: MonokaiTheme,
    pub messages: Vec<ChatMessage>,
    pub config: AppConfig,
    pub session_id: String,
    pub is_loading: bool,

    // Input component
    pub input_state: Entity<GpuiInputState>,

    // API client
    pub api_client: ApiClient,
    pub connection_status: ConnectionStatus,

    // Agent info
    pub agent_model: String,
    pub agent_provider: String,
    pub agent_skills: Vec<String>,
    pub agent_tools: Vec<String>,

    // User management
    pub current_user_id: String,
    pub available_users: Vec<String>,
    pub show_user_dropdown: bool,

    // Collapsible panel states
    pub memory_expanded: bool,
    pub knowledge_expanded: bool,
    pub tool_expanded: bool,

    // Real data from API (all user memories / global knowledge - for reference)
    pub memory_items: Vec<MemoryItem>,
    pub knowledge_triples: Vec<KnowledgeTriple>,
    pub current_tool_calls: Vec<ToolCall>,

    // Live tool calls (real-time updates during streaming)
    pub live_tool_calls: Vec<LiveToolCall>,

    // Context used for current query (what was actually loaded)
    pub current_context_memories: Vec<ContextMemory>,
    pub current_context_knowledge: Vec<ContextKnowledge>,

    // Streaming state
    pub streaming_content: String,
    pub streaming_message_id: Option<String>,
}

impl App {
    pub fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let api_client = ApiClient::new(None);
        let session_id = uuid::Uuid::new_v4().to_string()[..8].to_string();

        // Create input state with proper IME support
        let input_state = cx.new(|cx| {
            GpuiInputState::new(window, cx).placeholder("Type a message... (/ for commands)")
        });

        // Subscribe to input events for Enter key handling
        cx.subscribe_in(&input_state, window, |this, input_state: &Entity<GpuiInputState>, event: &InputEvent, window, cx| {
            if let InputEvent::PressEnter { .. } = event {
                let text = input_state.read(cx).value().to_string();
                input_state.update(cx, |state, cx| {
                    state.set_value("", window, cx);
                });
                this.send_message_with_text(text, cx);
            }
        })
        .detach();

        Self {
            theme: MonokaiTheme::new(),
            messages: vec![ChatMessage::system("Connecting to OmniEmployee backend...")],
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
            current_context_memories: vec![],
            current_context_knowledge: vec![],
            streaming_content: String::new(),
            streaming_message_id: None,
        }
    }

    pub fn initialize(&mut self, cx: &mut Context<Self>) {
        // Connect to API
        let api_client = self.api_client.clone();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_spawn(async move { api_client.get_agent_info() })
                .await;

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

    pub fn refresh_users(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_spawn(async move { api_client.get_users() })
                .await;
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

    pub fn switch_user(&mut self, user_id: String, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        let user_id_clone = user_id.clone();
        cx.spawn(async move |this, cx| {
            let result = cx
                .background_spawn(async move { api_client.switch_user(&user_id_clone) })
                .await;
            if let Ok(response) = result {
                if response.success {
                    let _ = this.update(cx, |app, cx| {
                        app.current_user_id = response.user_id;
                        app.show_user_dropdown = false;
                        app.session_id = uuid::Uuid::new_v4().to_string()[..8].to_string();
                        app.messages.clear();
                        app.messages.push(ChatMessage::system(format!(
                            "Switched to user: {}\nNew session started.",
                            app.current_user_id
                        )));
                        app.refresh_sidebar_data(cx);
                        cx.notify();
                    });
                }
            }
        })
        .detach();
    }

    pub fn refresh_sidebar_data(&mut self, _cx: &mut Context<Self>) {
        // Context data (memory/knowledge) is now loaded from stream events
        // when a query is sent, showing only what was used for that query.
        // This function is kept for backward compatibility but no longer
        // loads all memory/knowledge items.
    }

    pub fn handle_create_new_user(&mut self, cx: &mut Context<Self>) {
        let new_user_id = format!("user_{}", &uuid::Uuid::new_v4().to_string()[..8]);
        let api_client = self.api_client.clone();
        let user_id = new_user_id.clone();

        cx.spawn(async move |this, cx| {
            let result = cx
                .background_spawn(async move { api_client.create_user(&user_id) })
                .await;
            if let Ok(response) = result {
                if response.success {
                    let _ = this.update(cx, |app, cx| {
                        app.current_user_id = response.user_id.clone();
                        app.show_user_dropdown = false;
                        if !app.available_users.contains(&response.user_id) {
                            app.available_users.push(response.user_id.clone());
                        }
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
                    .child(self.render_messages(cx))
                    .child(self.render_input(window, cx)),
            )
            .child(self.render_sidebar(cx))
    }
}
