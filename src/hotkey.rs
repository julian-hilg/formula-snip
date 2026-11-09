//! Shortcut helpers: record a shortcut from an egui key press, and show it nicely.

use eframe::egui::{Key, Modifiers};
use global_hotkey::hotkey::{Code, HotKey};
use std::str::FromStr;

pub fn parse(s: &str) -> Option<HotKey> {
    HotKey::from_str(s).ok()
}

/// Build a shortcut string (e.g. "Ctrl+Semicolon") from a key press; needs at least one modifier.
pub fn from_press(key: Key, m: Modifiers) -> Option<String> {
    let code = to_code(key)?;
    let mut parts = Vec::new();
    if m.ctrl {
        parts.push("Ctrl");
    }
    if m.alt {
        parts.push("Alt");
    }
    if m.shift {
        parts.push("Shift");
    }
    if m.mac_cmd || (!cfg!(target_os = "macos") && m.command && !m.ctrl) {
        parts.push("Super");
    }
    if parts.is_empty() {
        return None;
    }
    let s = format!("{}+{}", parts.join("+"), code);
    parse(&s).map(|_| s)
}

/// "Ctrl+Alt+KeyM" -> "Ctrl+Alt+M" (macOS: "Ctrl+Option+M", "Cmd"). Punctuation keys also show
/// the German letter on that key, e.g. "Ctrl+; (Ö)".
pub fn pretty(s: &str) -> String {
    let mac = cfg!(target_os = "macos");
    s.split('+')
        .map(|p| match p.trim() {
            "Ctrl" | "Control" => "Ctrl".into(),
            "Alt" | "Option" => if mac { "Option" } else { "Alt" }.into(),
            "Shift" => "Shift".into(),
            "Super" | "Cmd" | "Command" => if mac { "Cmd" } else { "Win" }.into(),
            "Semicolon" => "; (Ö)".into(),
            "Quote" => "' (Ä)".into(),
            "BracketLeft" => "[ (Ü)".into(),
            k => k.trim_start_matches("Key").trim_start_matches("Digit").into(),
        })
        .collect::<Vec<String>>()
        .join("+")
}

fn to_code(key: Key) -> Option<Code> {
    use Code as C;
    Some(match key {
        Key::A => C::KeyA, Key::B => C::KeyB, Key::C => C::KeyC, Key::D => C::KeyD,
        Key::E => C::KeyE, Key::F => C::KeyF, Key::G => C::KeyG, Key::H => C::KeyH,
        Key::I => C::KeyI, Key::J => C::KeyJ, Key::K => C::KeyK, Key::L => C::KeyL,
        Key::M => C::KeyM, Key::N => C::KeyN, Key::O => C::KeyO, Key::P => C::KeyP,
        Key::Q => C::KeyQ, Key::R => C::KeyR, Key::S => C::KeyS, Key::T => C::KeyT,
        Key::U => C::KeyU, Key::V => C::KeyV, Key::W => C::KeyW, Key::X => C::KeyX,
        Key::Y => C::KeyY, Key::Z => C::KeyZ,
        Key::Num0 => C::Digit0, Key::Num1 => C::Digit1, Key::Num2 => C::Digit2,
        Key::Num3 => C::Digit3, Key::Num4 => C::Digit4, Key::Num5 => C::Digit5,
        Key::Num6 => C::Digit6, Key::Num7 => C::Digit7, Key::Num8 => C::Digit8,
        Key::Num9 => C::Digit9,
        Key::F1 => C::F1, Key::F2 => C::F2, Key::F3 => C::F3, Key::F4 => C::F4,
        Key::F5 => C::F5, Key::F6 => C::F6, Key::F7 => C::F7, Key::F8 => C::F8,
        Key::F9 => C::F9, Key::F10 => C::F10, Key::F11 => C::F11, Key::F12 => C::F12,
        Key::Semicolon => C::Semicolon, Key::Quote => C::Quote,
        Key::OpenBracket => C::BracketLeft, Key::CloseBracket => C::BracketRight,
        Key::Backslash => C::Backslash, Key::Backtick => C::Backquote,
        Key::Comma => C::Comma, Key::Period => C::Period, Key::Slash => C::Slash,
        Key::Minus => C::Minus, Key::Equals => C::Equal, Key::Space => C::Space,
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shortcuts_parse() {
        for s in ["Ctrl+Alt+KeyM", "Ctrl+Semicolon", "Ctrl+Shift+Digit1", "Super+Shift+F5"] {
            assert!(parse(s).is_some(), "{s} should parse");
        }
    }

    #[test]
    fn records_key_press() {
        let m = Modifiers { ctrl: true, ..Default::default() };
        assert_eq!(from_press(Key::Semicolon, m).as_deref(), Some("Ctrl+Semicolon"));
        assert_eq!(from_press(Key::Semicolon, Modifiers::NONE), None);
    }
}
