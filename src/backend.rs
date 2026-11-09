//! The OCR backend: a long-running Python process (`backend/ocr_server.py`, embedded in
//! the binary) that keeps the marker/surya model loaded. One JSON object per line.

use anyhow::{anyhow, bail, Context, Result};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{channel, Receiver};
use std::time::Duration;

const SERVER_PY: &str = include_str!("../backend/ocr_server.py");

pub struct Backend {
    child: Child,
    stdin: ChildStdin,
    lines: Receiver<String>,
}

pub fn log_path() -> PathBuf {
    crate::config::app_dir(dirs::data_local_dir()).join("backend.log")
}

impl Backend {
    /// Start the Python helper and wait until the model is loaded
    /// (first run downloads the model weights, so allow a few minutes).
    pub fn start(python: &Path) -> Result<Self> {
        let script = crate::config::app_dir(dirs::data_local_dir()).join("ocr_server.py");
        std::fs::write(&script, SERVER_PY)?;
        let log = std::fs::File::create(log_path())?;

        let mut cmd = Command::new(python);
        cmd.arg("-u")
            .arg(&script)
            .env("PATH", search_path())
            .env("TQDM_DISABLE", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(log);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        let mut child = cmd
            .spawn()
            .with_context(|| format!("could not start Python at {}", python.display()))?;

        let stdin = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let (tx, lines) = channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if tx.send(line).is_err() {
                    break;
                }
            }
        });

        let mut backend = Self { child, stdin, lines };
        let hello = backend.next(Duration::from_secs(600))?;
        if hello["ready"].as_bool() != Some(true) {
            bail!("{}", hello["error"].as_str().unwrap_or("model failed to load"));
        }
        Ok(backend)
    }

    pub fn recognize(&mut self, image: &Path) -> Result<String> {
        writeln!(self.stdin, "{}", image.display())?;
        self.stdin.flush()?;
        let reply = self.next(Duration::from_secs(120))?;
        match reply["ok"].as_bool() {
            Some(true) => Ok(reply["latex"].as_str().unwrap_or_default().to_string()),
            _ => bail!("{}", reply["error"].as_str().unwrap_or("recognition failed")),
        }
    }

    fn next(&mut self, timeout: Duration) -> Result<Value> {
        loop {
            let line = self.lines.recv_timeout(timeout).map_err(|_| {
                anyhow!("OCR helper stopped or timed out — see {}", log_path().display())
            })?;
            if let Ok(v) = serde_json::from_str::<Value>(&line) {
                return Ok(v);
            }
        }
    }
}

/// Apps started from Finder, the Start menu or at login get a minimal PATH, so the OCR
/// helper can't find `llama-server` (installed by Homebrew/winget). Add the usual places.
fn search_path() -> std::ffi::OsString {
    let home = dirs::home_dir().unwrap_or_default();
    let mut dirs: Vec<PathBuf> = std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();
    let extra: Vec<PathBuf> = if cfg!(windows) {
        let local = dirs::data_local_dir().unwrap_or_default();
        vec![local.join("Microsoft/WinGet/Links"), home.join("scoop/shims")]
    } else {
        vec![
            "/opt/homebrew/bin".into(),
            "/usr/local/bin".into(),
            "/home/linuxbrew/.linuxbrew/bin".into(),
            home.join(".linuxbrew/bin"),
            home.join(".local/bin"),
            "/usr/bin".into(),
            "/bin".into(),
        ]
    };
    for d in extra {
        if !dirs.contains(&d) {
            dirs.push(d);
        }
    }
    std::env::join_paths(dirs).unwrap_or_default()
}

impl Drop for Backend {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
