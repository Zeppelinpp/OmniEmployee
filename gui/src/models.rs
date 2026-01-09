//! Data models for OmniEmployee GUI

use crate::api::ToolCall;

/// Message role in conversation
#[derive(Debug, Clone, PartialEq)]
pub enum MessageRole {
    User,
    Assistant,
    System,
}

/// Inline tool call for streaming display
#[derive(Debug, Clone)]
pub struct InlineToolCall {
    pub id: String,
    pub name: String,
    pub arguments: serde_json::Value,
    pub result: Option<String>,
    pub status: ToolStatus,
    pub expanded: bool,
}

/// A segment of message content (text or tool call)
#[derive(Debug, Clone)]
pub enum MessageSegment {
    Text(String),
    ToolCall(InlineToolCall),
}

/// Chat message data
#[derive(Debug, Clone)]
pub struct ChatMessage {
    pub id: String,
    pub role: MessageRole,
    pub content: String,
    pub timestamp: String,
    pub tool_calls: Vec<ToolCall>,
    /// Segments for inline display (text interspersed with tool calls)
    pub segments: Vec<MessageSegment>,
}

impl ChatMessage {
    pub fn user(content: impl Into<String>) -> Self {
        let content_str = content.into();
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::User,
            content: content_str.clone(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
            segments: vec![MessageSegment::Text(content_str)],
        }
    }

    pub fn assistant(content: impl Into<String>, tool_calls: Vec<ToolCall>) -> Self {
        let content_str = content.into();
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::Assistant,
            content: content_str.clone(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls,
            segments: vec![MessageSegment::Text(content_str)],
        }
    }

    pub fn system(content: impl Into<String>) -> Self {
        let content_str = content.into();
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::System,
            content: content_str.clone(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
            segments: vec![MessageSegment::Text(content_str)],
        }
    }

    /// Create an empty assistant message for streaming
    pub fn assistant_streaming() -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            role: MessageRole::Assistant,
            content: String::new(),
            timestamp: chrono::Local::now().format("%H:%M").to_string(),
            tool_calls: vec![],
            segments: vec![],
        }
    }

    /// Append text to the last text segment or create a new one
    pub fn append_text(&mut self, text: &str) {
        self.content.push_str(text);
        if let Some(MessageSegment::Text(ref mut s)) = self.segments.last_mut() {
            s.push_str(text);
        } else {
            self.segments.push(MessageSegment::Text(text.to_string()));
        }
    }

    /// Add a tool call segment
    pub fn add_tool_call(&mut self, tool: InlineToolCall) {
        self.segments.push(MessageSegment::ToolCall(tool));
    }

    /// Update a tool call result by id
    pub fn update_tool_result(&mut self, tool_id: &str, result: String, status: ToolStatus) {
        for seg in &mut self.segments {
            if let MessageSegment::ToolCall(ref mut tc) = seg {
                if tc.id == tool_id {
                    tc.result = Some(result);
                    tc.status = status;
                    break;
                }
            }
        }
    }

    /// Toggle tool call expansion by id
    pub fn toggle_tool_expanded(&mut self, tool_id: &str) {
        for seg in &mut self.segments {
            if let MessageSegment::ToolCall(ref mut tc) = seg {
                if tc.id == tool_id {
                    tc.expanded = !tc.expanded;
                    break;
                }
            }
        }
    }

    /// Rebuild content from segments (for final message)
    pub fn rebuild_content(&mut self) {
        let mut content = String::new();
        for seg in &self.segments {
            if let MessageSegment::Text(ref s) = seg {
                content.push_str(s);
            }
        }
        self.content = content;
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
    pub fn parse(input: &str) -> Option<Self> {
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

/// Tool execution status
#[derive(Debug, Clone, PartialEq)]
pub enum ToolStatus {
    Running,
    Completed,
    Failed,
}
