//! API client for communicating with OmniEmployee backend

use anyhow::Result;
use serde::{Deserialize, Serialize};

const DEFAULT_API_URL: &str = "http://localhost:8765";

/// API response for chat messages
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatResponse {
    pub message: String,
    pub tool_calls: Vec<ToolCall>,
}

/// Tool call information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub name: String,
    pub result: Option<String>,
    pub success: bool,
}

/// Memory item from BIEM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryItem {
    pub id: String,
    pub content: String,
    pub energy: f32,
    pub tier: String,
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

/// API client for OmniEmployee backend
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
}
