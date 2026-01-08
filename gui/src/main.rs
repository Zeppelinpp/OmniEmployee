//! OmniEmployee GUI - A beautiful AI assistant interface
//!
//! Built with GPUI and Monokai Pro theme

mod theme;
mod api;

use gpui::{
    prelude::FluentBuilder,
    AppContext, Application, Bounds, Context, FocusHandle, FontWeight, Hsla,
    InteractiveElement, IntoElement, ParentElement, Render, SharedString,
    StatefulInteractiveElement, Styled, Window, WindowBounds, WindowOptions,
    TitlebarOptions, div, px, size,
};
use theme::MonokaiTheme;

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
}

impl ChatMessage {
    pub fn user(content: impl Into<String>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::User,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
        }
    }

    pub fn assistant(content: impl Into<String>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::Assistant,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
        }
    }

    pub fn system(content: impl Into<String>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::System,
            content: content.into(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
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

/// Main application state
pub struct App {
    theme: MonokaiTheme,
    messages: Vec<ChatMessage>,
    config: AppConfig,
    #[allow(dead_code)]
    session_id: String,
    is_loading: bool,
    input_text: String,
    focus_handle: FocusHandle,
    
    // Collapsible panel states
    memory_expanded: bool,
    knowledge_expanded: bool,
    tool_expanded: bool,
}

impl App {
    fn new(cx: &mut Context<Self>) -> Self {
        Self {
            theme: MonokaiTheme::new(),
            messages: vec![ChatMessage::system(
                "Welcome to OmniEmployee! Type a message or use /help for commands.",
            )],
            config: AppConfig::default(),
            session_id: uuid::Uuid::new_v4().to_string(),
            is_loading: false,
            input_text: String::new(),
            focus_handle: cx.focus_handle(),
            memory_expanded: false,
            knowledge_expanded: false,
            tool_expanded: true, // Tool use expanded by default
        }
    }

    #[allow(dead_code)]
    fn handle_command(&mut self, command: Command, cx: &mut Context<Self>) {
        let response = match command {
            Command::Help => {
                "**Available Commands:**\n\n\
                /stats - Show agent statistics\n\
                /memory - Show memory statistics\n\
                /knowledge - Show learned knowledge\n\
                /clear - Clear conversation\n\
                /config <key> <value> - Update config\n\n\
                Config keys: show_memory, show_knowledge, show_tools"
                    .to_string()
            }
            Command::Stats => {
                "📊 **Agent Statistics**\n\n\
                Model: gpt-4o\n\
                Provider: OpenAI\n\
                Skills: book-flight, codebase-tools, research\n\
                Tools: grep, read_file, write_file, run_command, web_search"
                    .to_string()
            }
            Command::Memory => {
                "🧠 **Memory Statistics**\n\n\
                L1 Working: 5 nodes\n\
                L2 Vector: 42 nodes\n\
                L3 Facts: 12\n\
                L3 Links: 28"
                    .to_string()
            }
            Command::Knowledge => {
                "📚 **Knowledge Statistics**\n\n\
                Total triples: 15\n\
                Unique subjects: 8\n\
                Unique predicates: 6\n\
                Pending confirmations: 0"
                    .to_string()
            }
            Command::Clear => {
                self.messages.clear();
                self.messages.push(ChatMessage::system("Conversation cleared."));
                cx.notify();
                return;
            }
            Command::Config { key, value } => {
                match key.as_str() {
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
                }
            }
            Command::Unknown(cmd) => {
                format!("Unknown command: /{}. Type /help for help.", cmd)
            }
        };

        self.messages.push(ChatMessage::system(response));
        cx.notify();
    }

    fn render_header(&self) -> impl IntoElement {
        let theme = &self.theme;

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
                                    .child("AI Assistant"),
                            ),
                    ),
            )
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_4()
                    .child(self.render_status_dot("Memory", self.config.show_memory))
                    .child(self.render_status_dot("Knowledge", self.config.show_knowledge)),
            )
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
                    .bg(if active { theme.accent_green } else { theme.foreground_muted }),
            )
            .child(
                div()
                    .text_xs()
                    .text_color(theme.foreground_dim)
                    .child(label),
            )
    }

    fn render_messages(&self) -> impl IntoElement {
        let theme = &self.theme;

        div()
            .id("messages-container")
            .flex_1()
            .overflow_y_scroll()
            .bg(theme.background)
            .p_4()
            .children(self.messages.iter().map(|msg| {
                let (bg_color, align_end, role_label, role_color) = match msg.role {
                    MessageRole::User => (
                        theme.user_message_bg,
                        true,
                        "You",
                        theme.accent_green,
                    ),
                    MessageRole::Assistant => (
                        theme.assistant_message_bg,
                        false,
                        "Assistant",
                        theme.accent_cyan,
                    ),
                    MessageRole::System => (
                        theme.system_message_bg,
                        false,
                        "System",
                        theme.accent_yellow,
                    ),
                };

                div()
                    .w_full()
                    .flex()
                    .mb_3()
                    .when(align_end, |el| el.justify_end())
                    .when(!align_end, |el| el.justify_start())
                    .child(
                        div()
                            .max_w(px(500.))
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
                                    .text_color(theme.foreground)
                                    .child(msg.content.clone()),
                            ),
                    )
            }))
    }

    fn render_collapsible_panel(
        &self,
        id: &'static str,
        icon: &'static str,
        title: &'static str,
        expanded: bool,
        color: Hsla,
        items: Vec<(&str, &str)>,
    ) -> impl IntoElement {
        let theme = &self.theme;
        let content_id = format!("{}-content", id);

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
                        .max_h(px(150.))
                        .overflow_y_scroll()
                        .bg(theme.background_secondary)
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
                                        .child(primary.to_string()),
                                )
                                .child(
                                    div()
                                        .text_xs()
                                        .text_color(theme.foreground_dim)
                                        .child(secondary.to_string()),
                                )
                        })),
                )
            })
    }

    fn render_sidebar(&self) -> impl IntoElement {
        let theme = &self.theme;

        div()
            .w(px(280.))
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
                    // Tool Use Panel
                    .when(self.config.show_tool_use, |el| {
                        el.child(self.render_collapsible_panel(
                            "tools",
                            "🔧",
                            "Tool Use",
                            self.tool_expanded,
                            theme.accent_orange,
                            vec![
                                ("read_file", "src/main.rs"),
                                ("grep", "search pattern"),
                            ],
                        ))
                    })
                    // Memory Panel
                    .when(self.config.show_memory, |el| {
                        el.child(self.render_collapsible_panel(
                            "memory",
                            "🧠",
                            "Memory",
                            self.memory_expanded,
                            theme.accent_purple,
                            vec![
                                ("User is learning ML...", "E=0.85"),
                                ("Deep learning is...", "E=0.62"),
                            ],
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
                            vec![
                                ("(Python, created_by, Guido)", "v1"),
                                ("(GPT-4, context, 128k)", "v2"),
                            ],
                        ))
                    }),
            )
    }

    fn render_input(&self, window: &Window) -> impl IntoElement {
        let theme = &self.theme;
        let is_loading = self.is_loading;
        let input_text = self.input_text.clone();
        let is_focused = self.focus_handle.is_focused(window);

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
                        div()
                            .id("input-field")
                            .flex_1()
                            .px_4()
                            .py_2()
                            .rounded_lg()
                            .bg(theme.background)
                            .border_1()
                            .border_color(if is_focused {
                                theme.border_focus
                            } else {
                                theme.border
                            })
                            .track_focus(&self.focus_handle)
                            .child(
                                div()
                                    .text_sm()
                                    .text_color(if input_text.is_empty() {
                                        theme.foreground_muted
                                    } else {
                                        theme.foreground
                                    })
                                    .child(if input_text.is_empty() {
                                        "Type a message... (/ for commands)".to_string()
                                    } else {
                                        input_text
                                    }),
                            ),
                    )
                    .child(
                        div()
                            .id("send-btn")
                            .cursor_pointer()
                            .px_4()
                            .py_2()
                            .rounded_lg()
                            .bg(if is_loading {
                                theme.foreground_muted
                            } else {
                                theme.accent_cyan
                            })
                            .text_sm()
                            .font_weight(FontWeight::MEDIUM)
                            .text_color(theme.background)
                            .hover(|style| style.bg(theme.accent_cyan.opacity(0.8)))
                            .child(if is_loading { "..." } else { "Send" }),
                    ),
            )
            .child(
                div()
                    .mt_1()
                    .text_xs()
                    .text_color(theme.foreground_muted)
                    .child("Tip: /stats, /memory, /knowledge, /help"),
            )
    }
}

impl Render for App {
    fn render(&mut self, window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
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
                    .child(self.render_header())
                    .child(self.render_messages())
                    .child(self.render_input(window)),
            )
            .child(self.render_sidebar())
    }
}

fn main() {
    Application::new().run(|app| {
        let window_options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                None,
                size(px(1200.), px(800.)),
                app,
            ))),
            titlebar: Some(TitlebarOptions {
                title: Some(SharedString::from("OmniEmployee")),
                ..Default::default()
            }),
            ..Default::default()
        };

        app.open_window(window_options, |window, cx| {
            let focus_handle = cx.focus_handle();
            focus_handle.focus(window, cx);
            cx.new(App::new)
        })
        .unwrap();
    });
}
