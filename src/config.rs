//! Settings, stored as JSON in the OS config dir:
//! macOS `~/Library/Application Support/formula-snip/config.json`,
//! Linux `~/.config/formula-snip/config.json`, Windows `%APPDATA%\formula-snip\config.json`.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Global shortcut, e.g. "Ctrl+Alt+KeyM". Empty until you pick one in Settings.
    /// Keys are *physical* key names, so they work the same on every keyboard layout.
    pub hotkey: String,
    /// Python interpreter that has `marker-pdf` installed. Empty = auto-detect.
    pub python: String,
    /// Open the panel after every snip.
    pub show_panel_after_snip: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            hotkey: String::new(),
            python: String::new(),
            show_panel_after_snip: true,
        }
    }
}

pub fn app_dir(base: Option<PathBuf>) -> PathBuf {
    let dir = base.unwrap_or_else(std::env::temp_dir).join("formula-snip");
    let _ = std::fs::create_dir_all(&dir);
    dir
}

fn path() -> PathBuf {
    app_dir(dirs::config_dir()).join("config.json")
}

impl Config {
    pub fn load() -> Self {
        std::fs::read_to_string(path())
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    pub fn save(&self) {
        if let Ok(s) = serde_json::to_string_pretty(self) {
            let _ = std::fs::write(path(), s);
        }
    }

    /// The configured Python, or the usual `pipx install marker-pdf` location, or `python3`.
    pub fn python_path(&self) -> PathBuf {
        if !self.python.trim().is_empty() {
            return PathBuf::from(self.python.trim());
        }
        let home = dirs::home_dir().unwrap_or_default();
        let candidates: &[&str] = if cfg!(windows) {
            &["pipx/venvs/marker-pdf/Scripts/python.exe", ".local/pipx/venvs/marker-pdf/Scripts/python.exe"]
        } else {
            &[".local/pipx/venvs/marker-pdf/bin/python", ".local/share/pipx/venvs/marker-pdf/bin/python"]
        };
        candidates
            .iter()
            .map(|c| home.join(c))
            .find(|p| p.exists())
            .unwrap_or_else(|| PathBuf::from(if cfg!(windows) { "python" } else { "python3" }))
    }
}
