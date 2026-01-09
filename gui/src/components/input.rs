//! Input component for OmniEmployee GUI

use gpui::{
    div, prelude::FluentBuilder, ClickEvent, Context, FontWeight, InteractiveElement, IntoElement,
    ParentElement, StatefulInteractiveElement, Styled, Window,
};
use gpui_component::input::Input;

use crate::app::App;
use crate::models::ConnectionStatus;

impl App {
    pub fn render_input(&self, _window: &Window, cx: &Context<Self>) -> impl IntoElement {
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
                        div().flex_1().child(
                            Input::new(&self.input_state).appearance(false), // Remove default styling
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

    pub fn handle_send_click(
        &mut self,
        _event: &ClickEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let text = self.input_state.read(cx).value().to_string();
        self.input_state.update(cx, |state, cx| {
            state.set_value("", window, cx);
        });
        self.send_message_with_text(text, cx);
    }
}
