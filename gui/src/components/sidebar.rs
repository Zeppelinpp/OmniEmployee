//! Sidebar component for OmniEmployee GUI

use gpui::{
    div, prelude::FluentBuilder, px, ClickEvent, Context, FontWeight, Hsla, InteractiveElement,
    IntoElement, ParentElement, SharedString, StatefulInteractiveElement, Styled, Window,
};
use gpui_component::text::TextView;

use crate::app::App;
use crate::models::ToolStatus;

impl App {
    pub fn render_sidebar(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;

        // Prepare memory items from current context (what was used for this query)
        let memory_items: Vec<(String, String)> = self
            .current_context_memories
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

        // Prepare knowledge items from current context (what was used for this query)
        let knowledge_items: Vec<(String, String)> = self
            .current_context_knowledge
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
                            .child("Query Context"),
                    )
                    .child(
                        div()
                            .text_xs()
                            .text_color(theme.foreground_muted)
                            .child("Used for current query"),
                    ),
            )
            .child(
                div()
                    .id("sidebar-panels")
                    .flex_1()
                    .overflow_y_scroll()
                    .p_3()
                    .when(self.config.show_tool_use, |el| {
                        el.child(self.render_live_tool_panel(cx))
                    })
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

    pub fn render_collapsible_panel(
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
                                .when(!is_last, |el| el.border_b_1().border_color(theme.border))
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

    pub fn render_live_tool_panel(&self, cx: &Context<Self>) -> impl IntoElement {
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
                            .when(!is_last, |inner| inner.border_b_1().border_color(theme.border))
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
                                        let result_view = TextView::markdown(
                                            SharedString::from(format!("tool-result-{}", tc.id)),
                                            result_content.clone(),
                                        );
                                        let result_container_id =
                                            format!("tool-result-container-{}", tc.id);

                                        inner.child(
                                            div()
                                                .id(SharedString::from(result_container_id))
                                                .mt_2()
                                                .p_2()
                                                .rounded(px(4.))
                                                .bg(theme.background)
                                                .max_h(px(300.))
                                                .overflow_y_scroll()
                                                .child(
                                                    div()
                                                        .text_xs()
                                                        .text_color(theme.foreground_muted)
                                                        .font_weight(FontWeight::MEDIUM)
                                                        .mb_1()
                                                        .child("Result:"),
                                                )
                                                .child(div().text_xs().child(result_view)),
                                        )
                                    }),
                            )
                    }));
                el.child(content)
            })
    }

    pub fn toggle_memory(&mut self, _: &ClickEvent, _window: &mut Window, cx: &mut Context<Self>) {
        self.memory_expanded = !self.memory_expanded;
        cx.notify();
    }

    pub fn toggle_knowledge(
        &mut self,
        _: &ClickEvent,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.knowledge_expanded = !self.knowledge_expanded;
        cx.notify();
    }

    pub fn toggle_tools(&mut self, _: &ClickEvent, _window: &mut Window, cx: &mut Context<Self>) {
        self.tool_expanded = !self.tool_expanded;
        cx.notify();
    }

    pub fn toggle_tool_call(
        &mut self,
        tool_id: String,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if let Some(tc) = self.live_tool_calls.iter_mut().find(|t| t.id == tool_id) {
            tc.expanded = !tc.expanded;
            cx.notify();
        }
    }
}
