//! Command and message handling for OmniEmployee GUI

use gpui::{AppContext as _, AsyncApp, Context};
use regex::Regex;

use crate::api::{StreamEvent, ToolCall};
use crate::app::App;
use crate::models::{ChatMessage, Command, ConnectionStatus, InlineToolCall, LiveToolCall, MessageRole, ToolStatus};

impl App {
    /// Send a message and process the response via streaming
    pub fn send_message_with_text(&mut self, text: String, cx: &mut Context<Self>) {
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
        self.live_tool_calls.clear();

        // Create streaming assistant message placeholder with segments
        let stream_msg = ChatMessage::assistant_streaming();
        let stream_msg_id = stream_msg.id.clone();
        self.streaming_message_id = Some(stream_msg_id.clone());
        self.streaming_content.clear();
        self.messages.push(stream_msg);
        cx.notify();

        // Send to API with streaming
        let api_client = self.api_client.clone();
        let session_id = self.session_id.clone();
        let message = text.clone();

        let (tx, rx) = std::sync::mpsc::channel::<StreamEvent>();

        cx.spawn(async move |this, cx| {
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
                        Self::handle_stream_event(&this, cx, event);
                        // Check if we should break (Done or Error)
                        if let Ok(should_break) = this.read_with(cx, |app, _| {
                            !app.is_loading
                        }) {
                            if should_break {
                                break;
                            }
                        }
                    }
                    Err(std::sync::mpsc::TryRecvError::Empty) => {
                        smol::Timer::after(std::time::Duration::from_millis(10)).await;
                    }
                    Err(std::sync::mpsc::TryRecvError::Disconnected) => {
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

    fn handle_stream_event(
        this: &gpui::WeakEntity<App>,
        cx: &mut AsyncApp,
        event: StreamEvent,
    ) {
        match event {
            StreamEvent::Context { memories, knowledge } => {
                let _ = this.update(cx, |app, cx| {
                    // Update sidebar with context used for this query
                    app.current_context_memories = memories;
                    app.current_context_knowledge = knowledge;
                    cx.notify();
                });
            }
            StreamEvent::Chunk { content } => {
                let _ = this.update(cx, |app, cx| {
                    app.streaming_content.push_str(&content);
                    if let Some(msg) = app.messages.last_mut() {
                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                            // Append text to the message segments
                            msg.append_text(&content);
                        }
                    }
                    cx.notify();
                });
            }
            StreamEvent::ToolStart { name, arguments, id } => {
                let _ = this.update(cx, |app, cx| {
                    // Add to live_tool_calls for sidebar (backward compat)
                    if !app.live_tool_calls.iter().any(|tc| tc.id == id) {
                        app.live_tool_calls.push(LiveToolCall {
                            id: id.clone(),
                            name: name.clone(),
                            arguments: arguments.clone(),
                            result: None,
                            status: ToolStatus::Running,
                            expanded: true,
                        });
                        app.tool_expanded = true;
                    }

                    // Add inline tool call to current streaming message
                    if let Some(msg) = app.messages.last_mut() {
                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                            msg.add_tool_call(InlineToolCall {
                                id,
                                name,
                                arguments,
                                result: None,
                                status: ToolStatus::Running,
                                expanded: true, // Start expanded to show progress
                            });
                        }
                    }
                    cx.notify();
                });
            }
            StreamEvent::ToolResult { id, result } => {
                let _ = this.update(cx, |app, cx| {
                    // Update sidebar tool calls
                    if let Some(tc) = app.live_tool_calls.iter_mut().find(|tc| tc.id == id) {
                        tc.result = Some(result.clone());
                        tc.status = ToolStatus::Completed;
                    }

                    // Update inline tool call in message
                    if let Some(msg) = app.messages.last_mut() {
                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                            msg.update_tool_result(&id, result, ToolStatus::Completed);
                        }
                    }
                    cx.notify();
                });
            }
            StreamEvent::Done { tool_calls } => {
                let _ = this.update(cx, |app, cx| {
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

                    // Mark all running tools as completed
                    for tc in &mut app.live_tool_calls {
                        if tc.status == ToolStatus::Running {
                            tc.status = ToolStatus::Completed;
                        }
                    }

                    if let Some(msg) = app.messages.last_mut() {
                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                            msg.tool_calls = tcs;
                            // Rebuild content from text segments
                            msg.rebuild_content();
                        }
                    }

                    app.is_loading = false;
                    app.streaming_message_id = None;
                    app.refresh_sidebar_data(cx);
                    cx.notify();
                });
            }
            StreamEvent::Error { content } => {
                let _ = this.update(cx, |app, cx| {
                    if let Some(msg) = app.messages.last_mut() {
                        if Some(&msg.id) == app.streaming_message_id.as_ref() {
                            msg.content = format!("⚠️ Error: {}", content);
                            msg.role = MessageRole::System;
                            msg.segments.clear();
                        }
                    }
                    // Mark all running tools as failed
                    for tc in &mut app.live_tool_calls {
                        if tc.status == ToolStatus::Running {
                            tc.status = ToolStatus::Failed;
                        }
                    }
                    app.is_loading = false;
                    app.streaming_message_id = None;
                    cx.notify();
                });
            }
        }
    }

    /// Handle slash commands
    pub fn handle_command(&mut self, command: Command, cx: &mut Context<Self>) {
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
            Command::Stats => self.handle_stats_command(cx),
            Command::Memory => self.handle_memory_command(cx),
            Command::Knowledge => self.handle_knowledge_command(cx),
            Command::Clear => self.handle_clear_command(cx),
            Command::Reconnect => {
                self.messages.clear();
                self.messages.push(ChatMessage::system("Reconnecting..."));
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

    fn handle_stats_command(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        self.messages.push(ChatMessage::system("Fetching stats..."));
        cx.notify();

        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move { api_client.get_agent_info() }).await;

            let mut stats_text = String::from("📊 **Agent Statistics**\n\n");
            if let Ok(info) = result {
                stats_text.push_str(&format!("Model: {}\n", info.model));
                stats_text.push_str(&format!("Provider: {}\n", info.provider));
                stats_text.push_str(&format!("Skills: {}\n", info.skills.join(", ")));
                stats_text.push_str(&format!("Tools: {}\n", info.tools.join(", ")));
                stats_text.push_str(&format!(
                    "Memory: {}\n",
                    if info.memory_enabled { "enabled" } else { "disabled" }
                ));
                stats_text.push_str(&format!(
                    "Knowledge: {}",
                    if info.knowledge_enabled { "enabled" } else { "disabled" }
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

    fn handle_memory_command(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        let user_id = self.current_user_id.clone();
        self.messages.push(ChatMessage::system("Fetching memory stats..."));
        cx.notify();

        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move { api_client.get_memory_stats(&user_id) }).await;

            let mut mem_text = String::from("🧠 **Memory Statistics** (per-user)\n\n");
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

    fn handle_knowledge_command(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        self.messages.push(ChatMessage::system("Fetching knowledge stats..."));
        cx.notify();

        cx.spawn(async move |this, cx| {
            let result = cx.background_spawn(async move { api_client.get_knowledge_stats() }).await;

            let mut know_text = String::from("📚 **Knowledge Statistics** (global, shared)\n\n");
            if let Ok(stats) = result {
                if stats.status.as_deref() == Some("unavailable") {
                    know_text.push_str("Knowledge system not available");
                } else {
                    know_text.push_str(&format!("Total triples: {}\n", stats.total_triples));
                    know_text.push_str(&format!("Unique subjects: {}\n", stats.unique_subjects));
                    know_text.push_str(&format!("Unique predicates: {}\n", stats.unique_predicates));
                    know_text.push_str(&format!("Total updates: {}\n", stats.total_updates));
                    know_text.push_str(&format!("Pending confirmations: {}", stats.pending_confirmations));
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

    fn handle_clear_command(&mut self, cx: &mut Context<Self>) {
        let api_client = self.api_client.clone();
        let session_id = self.session_id.clone();

        cx.spawn(async move |this, cx| {
            let _ = cx
                .background_spawn(async move { api_client.clear_chat(Some(session_id)) })
                .await;

            let _ = this.update(cx, |app, cx| {
                app.messages.clear();
                app.messages.push(ChatMessage::system("Conversation cleared."));
                app.current_tool_calls.clear();
                cx.notify();
            });
        })
        .detach();
    }

    /// Filter out tool call patterns from LLM response to keep it clean
    pub fn clean_response_content(content: &str) -> String {
        let mut result = content.to_string();

        let tool_block_patterns = [
            r"(?s)🔧\s*\*\*\w+\*\*.*?```[\s\S]*?```",
            r"🔧\s*\*\*\w+\*\*\s*\n_[^_]*\.\.\._",
            r"🔧\s*\*\*\w+\*\*",
            r"\[Summarized from \d+ chars\]",
            r"_[^_\n]+\.\.\._",
        ];

        for pattern in tool_block_patterns {
            if let Ok(re) = Regex::new(pattern) {
                result = re.replace_all(&result, "").to_string();
            }
        }

        if let Ok(re) = Regex::new(r"```\s*\n?\s*```") {
            result = re.replace_all(&result, "").to_string();
        }

        while result.contains("\n\n\n") {
            result = result.replace("\n\n\n", "\n\n");
        }

        result.trim().to_string()
    }
}
