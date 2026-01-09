//! Messages component for OmniEmployee GUI

use gpui::{
    div, prelude::FluentBuilder, px, Context, FontWeight, InteractiveElement, IntoElement,
    ParentElement, SharedString, StatefulInteractiveElement, Styled,
};
use gpui_component::text::TextView;

use crate::app::App;
use crate::models::{MessageRole, MessageSegment, ToolStatus};

impl App {
    pub fn render_messages(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;

        let message_elements: Vec<_> = self
            .messages
            .iter()
            .enumerate()
            .map(|(msg_idx, msg)| {
                let (bg_color, align_end, role_label, role_color) = match msg.role {
                    MessageRole::User => (theme.user_message_bg, true, "You", theme.accent_green),
                    MessageRole::Assistant => {
                        (theme.assistant_message_bg, false, "Assistant", theme.accent_cyan)
                    }
                    MessageRole::System => {
                        (theme.system_message_bg, false, "System", theme.accent_yellow)
                    }
                };

                let msg_id = msg.id.clone();
                let is_streaming = self.streaming_message_id.as_ref() == Some(&msg.id);
                let use_segments = msg.role == MessageRole::Assistant && !msg.segments.is_empty();

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
                                    .when(use_segments, |el| {
                                        // Render segments inline (text + tool calls)
                                        el.children(msg.segments.iter().enumerate().map(|(seg_idx, seg)| {
                                            match seg {
                                                MessageSegment::Text(text) => {
                                                    let cleaned = Self::clean_response_content(text);
                                                    if cleaned.is_empty() {
                                                        div().into_any_element()
                                                    } else {
                                                        let content_view = TextView::markdown(
                                                            SharedString::from(format!("msg-{}-seg-{}", msg_idx, seg_idx)),
                                                            cleaned,
                                                        );
                                                        div().text_sm().child(content_view).into_any_element()
                                                    }
                                                }
                                                MessageSegment::ToolCall(tc) => {
                                                    let tool_id = tc.id.clone();
                                                    let msg_id_clone = msg_id.clone();
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

                                                    div()
                                                        .my_2()
                                                        .rounded_md()
                                                        .border_1()
                                                        .border_color(theme.border)
                                                        .bg(theme.background_secondary)
                                                        .overflow_hidden()
                                                        .child(
                                                            div()
                                                                .id(SharedString::from(format!("tool-header-{}", tc.id)))
                                                                .flex()
                                                                .items_center()
                                                                .gap_2()
                                                                .px_3()
                                                                .py_2()
                                                                .cursor_pointer()
                                                                .hover(|s| s.bg(theme.background_highlight))
                                                                .on_click(cx.listener(move |this, _event, _window, cx| {
                                                                    this.toggle_inline_tool(&msg_id_clone, &tool_id, cx);
                                                                }))
                                                                .child(
                                                                    div()
                                                                        .text_xs()
                                                                        .text_color(theme.foreground_muted)
                                                                        .child(if tc.expanded { "▼" } else { "▶" }),
                                                                )
                                                                .child(div().text_sm().child(status_icon))
                                                                .child(
                                                                    div()
                                                                        .text_sm()
                                                                        .font_weight(FontWeight::MEDIUM)
                                                                        .text_color(status_color)
                                                                        .child(format!("🔧 {}", tc.name)),
                                                                )
                                                                .when(tc.status == ToolStatus::Running, |el| {
                                                                    el.child(
                                                                        div()
                                                                            .text_xs()
                                                                            .text_color(theme.foreground_muted)
                                                                            .child("running...")
                                                                    )
                                                                }),
                                                        )
                                                        .when(tc.expanded, |el| {
                                                            let result_text = tc.result.clone().unwrap_or_else(|| {
                                                                if tc.status == ToolStatus::Running {
                                                                    "Executing...".to_string()
                                                                } else {
                                                                    "No result".to_string()
                                                                }
                                                            });
                                                            let truncated = if result_text.len() > 500 {
                                                                format!("{}...", &result_text[..500])
                                                            } else {
                                                                result_text
                                                            };
                                                            let result_view = TextView::markdown(
                                                                SharedString::from(format!("tool-result-{}", tc.id)),
                                                                truncated,
                                                            );

                                                            el.child(
                                                                div()
                                                                    .id(SharedString::from(format!("tool-content-{}", tc.id)))
                                                                    .px_3()
                                                                    .py_2()
                                                                    .border_t_1()
                                                                    .border_color(theme.border)
                                                                    .bg(theme.background)
                                                                    .max_h(px(200.))
                                                                    .overflow_y_scroll()
                                                                    .child(
                                                                        div()
                                                                            .text_xs()
                                                                            .text_color(theme.foreground_dim)
                                                                            .child(result_view)
                                                                    )
                                                            )
                                                        })
                                                        .into_any_element()
                                                }
                                            }
                                        }))
                                    })
                                    .when(!use_segments, |el| {
                                        // Fallback: render plain content
                                        let cleaned_content = Self::clean_response_content(&msg.content);
                                        let content_view = TextView::markdown(
                                            SharedString::from(format!("msg-{}", msg_idx)),
                                            cleaned_content,
                                        );
                                        el.child(div().text_sm().child(content_view))
                                    })
                                    .when(is_streaming && msg.segments.is_empty() && msg.content.is_empty(), |el| {
                                        el.child(
                                            div()
                                                .text_sm()
                                                .text_color(theme.foreground_muted)
                                                .child("Thinking...")
                                        )
                                    }),
                            ),
                    )
            })
            .collect();

        div()
            .id("messages-container")
            .flex_1()
            .overflow_y_scroll()
            .bg(theme.background)
            .p_4()
            .children(message_elements)
    }

    /// Toggle inline tool call expansion
    pub fn toggle_inline_tool(&mut self, msg_id: &str, tool_id: &str, cx: &mut Context<Self>) {
        if let Some(msg) = self.messages.iter_mut().find(|m| m.id == msg_id) {
            msg.toggle_tool_expanded(tool_id);
            cx.notify();
        }
    }
}
