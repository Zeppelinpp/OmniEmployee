//! Header component for OmniEmployee GUI

use gpui::{
    anchored, deferred, div, prelude::FluentBuilder, px, Context, FontWeight, Hsla,
    InteractiveElement, IntoElement, ParentElement, SharedString, StatefulInteractiveElement,
    Styled,
};

use crate::app::App;
use crate::models::ConnectionStatus;

impl App {
    pub fn render_header(&self, cx: &Context<Self>) -> impl IntoElement {
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

    pub fn render_user_selector(&self, cx: &Context<Self>) -> impl IntoElement {
        let theme = &self.theme;
        let current_user = self.current_user_id.clone();
        let show_dropdown = self.show_user_dropdown;
        let users = self.available_users.clone();

        div()
            .id("user-selector")
            .child(
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
                this.child(deferred(anchored().child(
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
                        .children(users.into_iter().map(|user| {
                            let user_clone = user.clone();
                            let is_current = user == self.current_user_id;
                            div()
                                .id(SharedString::from(format!("user-{}", user)))
                                .w_full()
                                .px_3()
                                .py_2()
                                .cursor_pointer()
                                .text_sm()
                                .text_color(if is_current {
                                    theme.accent_cyan
                                } else {
                                    theme.foreground
                                })
                                .bg(if is_current {
                                    theme.background_highlight
                                } else {
                                    theme.background_elevated
                                })
                                .hover(|s| s.bg(theme.background_highlight))
                                .on_click(cx.listener(move |this, _event, _window, cx| {
                                    this.switch_user(user_clone.clone(), cx);
                                }))
                                .child(SharedString::from(user))
                        }))
                        .child(div().h(px(1.)).w_full().bg(theme.border))
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
                )))
            })
    }

    pub fn render_status_indicator(&self, label: &'static str, color: Hsla) -> impl IntoElement {
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

    pub fn render_status_dot(&self, label: &'static str, active: bool) -> impl IntoElement {
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
}
