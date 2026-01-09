//! OmniEmployee GUI - A beautiful AI assistant interface
//!
//! Built with GPUI and Monokai Pro theme

mod api;
mod app;
mod components;
mod handlers;
mod models;
mod theme;

use app::App;
use gpui::{
    px, size, AppContext, Application, Bounds, SharedString, TitlebarOptions, WindowBounds,
    WindowOptions,
};
use gpui_component::Root;

fn main() {
    Application::new().run(|cx| {
        // Initialize gpui-component (required before using any component)
        gpui_component::init(cx);

        let window_options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(Bounds::centered(
                None,
                size(px(1200.), px(800.)),
                cx,
            ))),
            titlebar: Some(TitlebarOptions {
                title: Some(SharedString::from("OmniEmployee")),
                ..Default::default()
            }),
            ..Default::default()
        };

        cx.open_window(window_options, |window, cx| {
            // Create app with window reference for input component initialization
            let app_entity = cx.new(|cx| App::new(window, cx));

            // Initialize the app after creation (connect to backend)
            app_entity.update(cx, |app, cx| {
                app.initialize(cx);
            });

            // Focus the input after initialization
            app_entity.update(cx, |app, cx| {
                app.input_state.update(cx, |state, cx| {
                    state.focus(window, cx);
                });
            });

            // Wrap in Root for gpui-component theming support
            cx.new(|cx| Root::new(app_entity.clone(), window, cx))
        })
        .unwrap();
    });
}
