//! API client for communicating with OmniEmployee backend
//!
//! Uses blocking HTTP to avoid Tokio runtime conflicts with GPUI.

use anyhow::Result;
use serde::{Deserialize, Serialize};

const DEFAULT_API_URL: &str = "http://localhost:8765";

/// Chat request payload
#[derive(Debug, Clone, Serialize)]
pub struct ChatRequest {
    pub message: String,
    pub session_id: Option<String>,
}

/// API response for chat messages
#[derive(Debug, Clone, Deserialize)]
pub struct ChatResponse {
    pub response: String,
    pub tool_calls: Vec<ToolCall>,
    pub session_id: String,
}

/// Tool call information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub name: String,
    pub arguments: serde_json::Value,
    pub result: Option<String>,
    #[serde(default)]
    pub success: bool,
}

/// Agent info response
#[derive(Debug, Clone, Deserialize)]
pub struct AgentInfo {
    pub provider: String,
    pub model: String,
    pub skills: Vec<String>,
    pub tools: Vec<String>,
    pub memory_enabled: bool,
    pub knowledge_enabled: bool,
}

/// Memory item from BIEM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryItem {
    pub id: String,
    pub content: String,
    pub energy: f32,
    pub tier: String,
}

/// Memory context response
#[derive(Debug, Clone, Deserialize)]
pub struct MemoryContextResponse {
    pub items: Vec<MemoryItem>,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
}

/// Knowledge triple
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgeTriple {
    pub id: String,
    pub subject: String,
    pub predicate: String,
    pub object: String,
    pub confidence: f32,
    pub source: String,
}

/// Knowledge triples response
#[derive(Debug, Clone, Deserialize)]
pub struct KnowledgeTriplesResponse {
    pub triples: Vec<KnowledgeTriple>,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
}

/// Memory stats response
#[derive(Debug, Clone, Deserialize, Default)]
pub struct MemoryStats {
    #[serde(default)]
    pub l1_count: i64,
    #[serde(default)]
    pub l2_vector_count: i64,
    #[serde(default)]
    pub l2_graph_nodes: i64,
    #[serde(default)]
    pub l2_graph_edges: i64,
    #[serde(default)]
    pub l3_facts: i64,
    #[serde(default)]
    pub l3_links: i64,
}

/// Knowledge stats response
#[derive(Debug, Clone, Deserialize, Default)]
pub struct KnowledgeStats {
    #[serde(default)]
    pub total_triples: i64,
    #[serde(default)]
    pub unique_subjects: i64,
    #[serde(default)]
    pub unique_predicates: i64,
    #[serde(default)]
    pub total_updates: i64,
    #[serde(default)]
    pub pending_confirmations: i64,
    #[serde(default)]
    pub status: Option<String>,
}

/// Users list response
#[derive(Debug, Clone, Deserialize, Default)]
pub struct UsersResponse {
    pub users: Vec<String>,
    pub current: String,
}

/// User switch response
#[derive(Debug, Clone, Deserialize)]
pub struct UserSwitchResponse {
    pub success: bool,
    pub user_id: String,
}

/// Stream event types from SSE
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
pub enum StreamEvent {
    #[serde(rename = "chunk")]
    Chunk { content: String },
    #[serde(rename = "tool_start")]
    ToolStart {
        name: String,
        #[serde(default)]
        arguments: serde_json::Value,
        #[serde(default)]
        id: String,
    },
    #[serde(rename = "tool_result")]
    ToolResult {
        #[serde(default)]
        id: String,
        #[serde(default)]
        result: String,
    },
    #[serde(rename = "done")]
    Done {
        #[serde(default)]
        tool_calls: Vec<StreamToolCall>,
    },
    #[serde(rename = "error")]
    Error { content: String },
}

/// Tool call from stream
#[derive(Debug, Clone, Deserialize, Default)]
pub struct StreamToolCall {
    pub name: String,
    #[serde(default)]
    pub arguments: serde_json::Value,
}

/// API client for OmniEmployee backend (uses blocking HTTP)
#[derive(Clone)]
pub struct ApiClient {
    base_url: String,
}

impl ApiClient {
    pub fn new(base_url: Option<String>) -> Self {
        Self {
            base_url: base_url.unwrap_or_else(|| DEFAULT_API_URL.to_string()),
        }
    }

    pub fn get_base_url(&self) -> &str {
        &self.base_url
    }

    fn client(&self) -> reqwest::blocking::Client {
        reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()
            .unwrap_or_else(|_| reqwest::blocking::Client::new())
    }

    /// Send a chat message and get response (blocking)
    pub fn chat(&self, message: &str, session_id: Option<String>) -> Result<ChatResponse> {
        let url = format!("{}/api/chat", self.base_url);
        let request = ChatRequest {
            message: message.to_string(),
            session_id,
        };

        let response = self
            .client()
            .post(&url)
            .json(&request)
            .send()?
            .json::<ChatResponse>()?;

        Ok(response)
    }

    /// Get agent information (blocking)
    pub fn get_agent_info(&self) -> Result<AgentInfo> {
        let url = format!("{}/api/agent/info", self.base_url);
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Get memory context for a query (blocking)
    pub fn get_memory_context(&self, query: &str, limit: usize) -> Result<MemoryContextResponse> {
        let url = format!(
            "{}/api/memory/context?query={}&limit={}",
            self.base_url, query, limit
        );
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Get memory statistics (blocking)
    pub fn get_memory_stats(&self) -> Result<MemoryStats> {
        let url = format!("{}/api/stats", self.base_url);
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Get knowledge triples (blocking)
    pub fn get_knowledge_triples(&self, limit: usize) -> Result<KnowledgeTriplesResponse> {
        let url = format!("{}/api/knowledge/triples?limit={}", self.base_url, limit);
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Get knowledge statistics (blocking)
    pub fn get_knowledge_stats(&self) -> Result<KnowledgeStats> {
        let url = format!("{}/api/knowledge/stats", self.base_url);
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Get list of users (blocking)
    pub fn get_users(&self) -> Result<UsersResponse> {
        let url = format!("{}/api/users", self.base_url);
        let response = self.client().get(&url).send()?.json()?;
        Ok(response)
    }

    /// Switch to a different user (blocking)
    pub fn switch_user(&self, user_id: &str) -> Result<UserSwitchResponse> {
        let url = format!("{}/api/user/switch?user_id={}", self.base_url, urlencoding::encode(user_id));
        let response = self.client().post(&url).send()?.json()?;
        Ok(response)
    }

    /// Create a new user (blocking)
    pub fn create_user(&self, user_id: &str) -> Result<UserSwitchResponse> {
        let url = format!("{}/api/user/create?user_id={}", self.base_url, urlencoding::encode(user_id));
        let response = self.client().post(&url).send()?.json()?;
        Ok(response)
    }

    /// Clear conversation (blocking)
    pub fn clear_chat(&self, session_id: Option<String>) -> Result<()> {
        let url = format!(
            "{}/api/chat/clear?session_id={}",
            self.base_url,
            session_id.unwrap_or_default()
        );
        self.client().post(&url).send()?;
        Ok(())
    }

    /// Stream chat response with callback for each chunk
    pub fn chat_stream<F>(&self, message: &str, session_id: Option<String>, mut on_event: F) -> Result<Vec<ToolCall>>
    where
        F: FnMut(StreamEvent),
    {
        use std::io::BufRead;

        let url = format!(
            "{}/api/chat/stream?message={}&session_id={}",
            self.base_url,
            urlencoding::encode(message),
            session_id.unwrap_or_default()
        );

        let response = self.client().get(&url).send()?;
        let reader = std::io::BufReader::new(response);

        let mut tool_calls = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if line.starts_with("data: ") {
                let data = &line[6..];
                if let Ok(event) = serde_json::from_str::<StreamEvent>(data) {
                    match &event {
                        StreamEvent::Done { tool_calls: tcs } => {
                            tool_calls = tcs
                                .iter()
                                .map(|tc| ToolCall {
                                    name: tc.name.clone(),
                                    arguments: tc.arguments.clone(),
                                    result: None,
                                    success: true,
                                })
                                .collect();
                        }
                        _ => {}
                    }
                    on_event(event);
                }
            }
        }

        Ok(tool_calls)
    }
}
