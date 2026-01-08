//! Monokai Pro Theme for OmniEmployee GUI
//!
//! A faithful implementation of the Monokai Pro color scheme.

use gpui::{rgb, Hsla};

/// Monokai Pro color palette
pub mod colors {
    use gpui::rgb;

    // Background colors
    pub fn bg_dark() -> gpui::Hsla { rgb(0x19181a).into() }      // #19181a - Darkest background
    pub fn bg_base() -> gpui::Hsla { rgb(0x2d2a2e).into() }      // #2d2a2e - Main background
    pub fn bg_light() -> gpui::Hsla { rgb(0x403e41).into() }     // #403e41 - Lighter background
    pub fn bg_highlight() -> gpui::Hsla { rgb(0x5b595c).into() } // #5b595c - Highlight background

    // Foreground colors
    pub fn fg_base() -> gpui::Hsla { rgb(0xfcfcfa).into() }      // #fcfcfa - Main text
    pub fn fg_dim() -> gpui::Hsla { rgb(0x939293).into() }       // #939293 - Dimmed text
    pub fn fg_muted() -> gpui::Hsla { rgb(0x727072).into() }     // #727072 - Muted text

    // Accent colors (Monokai Pro)
    pub fn red() -> gpui::Hsla { rgb(0xff6188).into() }          // #ff6188 - Red/Pink
    pub fn orange() -> gpui::Hsla { rgb(0xfc9867).into() }       // #fc9867 - Orange
    pub fn yellow() -> gpui::Hsla { rgb(0xffd866).into() }       // #ffd866 - Yellow
    pub fn green() -> gpui::Hsla { rgb(0xa9dc76).into() }        // #a9dc76 - Green
    pub fn cyan() -> gpui::Hsla { rgb(0x78dce8).into() }         // #78dce8 - Cyan
    pub fn purple() -> gpui::Hsla { rgb(0xab9df2).into() }       // #ab9df2 - Purple

    // Border colors
    pub fn border() -> gpui::Hsla { rgb(0x403e41).into() }       // Same as BG_LIGHT
    pub fn border_focus() -> gpui::Hsla { rgb(0x78dce8).into() } // Cyan for focus

    // Scrollbar
    pub fn scrollbar_bg() -> gpui::Hsla { rgb(0x2d2a2e).into() }
    pub fn scrollbar_thumb() -> gpui::Hsla { rgb(0x5b595c).into() }
    pub fn scrollbar_thumb_hover() -> gpui::Hsla { rgb(0x727072).into() }
}

/// Theme configuration
#[derive(Clone)]
pub struct MonokaiTheme {
    // Backgrounds
    pub background: Hsla,
    pub background_secondary: Hsla,
    pub background_elevated: Hsla,
    pub background_highlight: Hsla,

    // Foregrounds
    pub foreground: Hsla,
    pub foreground_dim: Hsla,
    pub foreground_muted: Hsla,

    // Accents
    pub accent_red: Hsla,
    pub accent_orange: Hsla,
    pub accent_yellow: Hsla,
    pub accent_green: Hsla,
    pub accent_cyan: Hsla,
    pub accent_purple: Hsla,

    // Semantic
    pub success: Hsla,
    pub warning: Hsla,
    pub error: Hsla,
    pub info: Hsla,

    // UI
    pub border: Hsla,
    pub border_focus: Hsla,
    pub scrollbar_bg: Hsla,
    pub scrollbar_thumb: Hsla,
    pub scrollbar_thumb_hover: Hsla,

    // Message colors
    pub user_message_bg: Hsla,
    pub assistant_message_bg: Hsla,
    pub system_message_bg: Hsla,
}

impl Default for MonokaiTheme {
    fn default() -> Self {
        Self {
            // Backgrounds
            background: colors::bg_base(),
            background_secondary: colors::bg_dark(),
            background_elevated: colors::bg_light(),
            background_highlight: colors::bg_highlight(),

            // Foregrounds
            foreground: colors::fg_base(),
            foreground_dim: colors::fg_dim(),
            foreground_muted: colors::fg_muted(),

            // Accents
            accent_red: colors::red(),
            accent_orange: colors::orange(),
            accent_yellow: colors::yellow(),
            accent_green: colors::green(),
            accent_cyan: colors::cyan(),
            accent_purple: colors::purple(),

            // Semantic
            success: colors::green(),
            warning: colors::yellow(),
            error: colors::red(),
            info: colors::cyan(),

            // UI
            border: colors::border(),
            border_focus: colors::border_focus(),
            scrollbar_bg: colors::scrollbar_bg(),
            scrollbar_thumb: colors::scrollbar_thumb(),
            scrollbar_thumb_hover: colors::scrollbar_thumb_hover(),

            // Messages
            user_message_bg: colors::bg_light(),
            assistant_message_bg: colors::bg_dark(),
            system_message_bg: colors::bg_base(),
        }
    }
}

impl MonokaiTheme {
    pub fn new() -> Self {
        Self::default()
    }
}
