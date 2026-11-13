//! The Paper tab's worker: runs `convert.py convert … --json --stdin-control` in the
//! background and turns its JSON events into a state the panel draws.

use anyhow::{Context, Result};
use eframe::egui;
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

/// The panel converts at most this many pages per PDF (the command line has no limit).
pub const MAX_PAGES: u32 = 100;
/// Pages per marker batch: progress is reported and finished work kept per batch.
const BATCH_PAGES: u32 = 10;

#[derive(Clone, Default)]
pub enum Phase {
    #[default]
    Idle,
    Running { text: String, done: u32, total: u32 },
    Cancelling,
    Done { out: PathBuf, summary: Vec<String>, secs: f32 },
    Failed(String),
    Cancelled,
}

#[derive(Default)]
pub struct State {
    pub phase: Phase,
    /// File name of the PDF being converted (shown while it runs).
    pub pdf_name: String,
    stdin: Option<ChildStdin>,
    child: Option<Arc<Mutex<Child>>>,
}

impl State {
    pub fn running(&self) -> bool {
        matches!(self.phase, Phase::Running { .. } | Phase::Cancelling)
    }
}

pub fn log_path() -> PathBuf {
    crate::config::app_dir(dirs::data_local_dir()).join("paper.log")
}

/// `<dir>/<pdf name>`, or `<pdf name> (2)` … when that folder holds something else.
pub fn out_dir(dir: &Path, pdf: &Path) -> PathBuf {
    let stem = pdf.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "paper".into());
    let name = pdf.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
    for i in 1.. {
        let cand = if i == 1 { dir.join(&stem) } else { dir.join(format!("{stem} ({i})")) };
        let empty = std::fs::read_dir(&cand).map(|mut d| d.next().is_none()).unwrap_or(true);
        let ours = std::fs::read_to_string(cand.join("meta.json"))
            .ok()
            .and_then(|s| serde_json::from_str::<Value>(&s).ok())
            .is_some_and(|m| m["source"]["name"].as_str() == Some(name.as_str()));
        if !cand.exists() || empty || ours {
            return cand;
        }
    }
    unreachable!()
}

/// Start converting `pdf` into `out`. Progress lands in `state`.
pub fn start(python: &Path, pdf: &Path, out: &Path, pages: &str, state: Arc<Mutex<State>>, ctx: egui::Context) -> Result<()> {
    let mut args = vec![
        "convert".to_string(),
        pdf.display().to_string(),
        "--out".into(),
        out.display().to_string(),
        "--json".into(),
        "--stdin-control".into(),
        "--max-pages".into(),
        MAX_PAGES.to_string(),
        "--batch-pages".into(),
        BATCH_PAGES.to_string(),
    ];
    if !pages.trim().is_empty() {
        args.extend(["--pages".into(), pages.trim().to_string()]);
    }
    let log = std::fs::File::create(log_path())?;
    let mut cmd = crate::backend::tool_command(python, &args)?;
    cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(log);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = cmd.spawn().with_context(|| format!("could not start Python at {}", python.display()))?;
    let stdout = child.stdout.take().unwrap();
    let child = Arc::new(Mutex::new(child));
    {
        let mut s = state.lock().unwrap();
        s.stdin = child.lock().unwrap().stdin.take();
        s.child = Some(child.clone());
        s.pdf_name = pdf.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        s.phase = Phase::Running { text: "Starting …".into(), done: 0, total: 0 };
    }
    ctx.request_repaint();

    std::thread::spawn(move || {
        let t = Instant::now();
        let mut last: Option<Value> = None;
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let Ok(ev) = serde_json::from_str::<Value>(&line) else { continue };
            let mut s = state.lock().unwrap();
            if !matches!(s.phase, Phase::Cancelling) {
                if let Some(p) = progress(&ev) {
                    s.phase = p;
                }
            }
            drop(s);
            last = Some(ev);
            ctx.request_repaint();
        }
        // poll instead of wait(), so cancel() can still lock the child and kill it
        let code = loop {
            match child.lock().unwrap().try_wait() {
                Ok(Some(status)) => break status.code(),
                Ok(None) => {}
                Err(_) => break None,
            }
            std::thread::sleep(Duration::from_millis(100));
        };
        let mut s = state.lock().unwrap();
        s.stdin = None;
        s.child = None;
        s.phase = match (&last, code) {
            (Some(ev), Some(0)) if ev["event"] == "done" => Phase::Done {
                out: PathBuf::from(ev["out"].as_str().unwrap_or_default()),
                summary: summary(&ev["meta"]["summary"]),
                secs: t.elapsed().as_secs_f32(),
            },
            (Some(ev), _) if ev["event"] == "cancelled" => Phase::Cancelled,
            _ if matches!(s.phase, Phase::Cancelling) => Phase::Cancelled,
            (Some(ev), _) if ev["event"] == "error" => Phase::Failed(ev["error"].as_str().unwrap_or("failed").to_string()),
            _ => Phase::Failed(format!("the converter stopped unexpectedly, see {}", crate::app::tilde(&log_path()))),
        };
        ctx.request_repaint();
    });
    Ok(())
}

/// Ask the converter to stop (it finishes marker's current step and shuts the model
/// server down). Killed if it hasn't exited after 20 s.
pub fn cancel(state: &Arc<Mutex<State>>) {
    let mut s = state.lock().unwrap();
    if !s.running() {
        return;
    }
    s.phase = Phase::Cancelling;
    if let Some(mut stdin) = s.stdin.take() {
        let _ = writeln!(stdin, "cancel");
    }
    if let Some(child) = s.child.clone() {
        std::thread::spawn(move || {
            let t = Instant::now();
            while t.elapsed() < Duration::from_secs(20) {
                if child.lock().unwrap().try_wait().ok().flatten().is_some() {
                    return;
                }
                std::thread::sleep(Duration::from_millis(200));
            }
            let _ = child.lock().unwrap().kill();
        });
    }
}

fn progress(ev: &Value) -> Option<Phase> {
    let text = |t: &str| Some(Phase::Running { text: t.to_string(), done: 0, total: 0 });
    match ev["event"].as_str()? {
        "start" => text("Reading the PDF …"),
        "progress" => match ev["stage"].as_str()? {
            "loading_models" => text("Loading the OCR model …"),
            "cached" => text("Already converted, using the cache …"),
            "formulas" => text("Building the formula registry …"),
            "converting" | "resumed" => {
                let pages = ev["pages"].as_array()?;
                let (a, b) = (pages.first()?.as_u64()?, pages.last()?.as_u64()?);
                Some(Phase::Running {
                    text: format!("Pages {a}-{b} (batch {} of {})", ev["batch"], ev["batches"]),
                    done: ev["done_pages"].as_u64()? as u32,
                    total: ev["total_pages"].as_u64()? as u32,
                })
            }
            _ => None,
        },
        _ => None,
    }
}

fn summary(s: &Value) -> Vec<String> {
    let n = |k: &str| s[k].as_u64().unwrap_or(0);
    vec![
        format!("{} formulas ({} display, {} inline, {} numbered)", n("formulas"), n("display"), n("inline"), n("numbered")),
        format!("{} as Python functions, {} unparsed", n("parsed"), n("unparsed")),
        format!("{} symbols, {} with a definition", n("variables"), n("variables_defined")),
    ]
}

/// Open a file or folder with the system's default app.
pub fn open(path: &Path) {
    #[cfg(target_os = "macos")]
    let r = std::process::Command::new("open").arg(path).spawn();
    #[cfg(target_os = "windows")]
    let r = std::process::Command::new("explorer").arg(path).spawn();
    #[cfg(all(unix, not(target_os = "macos")))]
    let r = std::process::Command::new("xdg-open").arg(path).spawn();
    let _ = r;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("formula-snip-test-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn out_dir_never_reuses_foreign_folders() {
        let d = tmp("outdir");
        let pdf = Path::new("/x/My Paper.pdf");
        assert_eq!(out_dir(&d, pdf), d.join("My Paper"));
        std::fs::create_dir_all(d.join("My Paper")).unwrap();
        assert_eq!(out_dir(&d, pdf), d.join("My Paper")); // empty: fine
        std::fs::write(d.join("My Paper/notes.txt"), "mine").unwrap();
        assert_eq!(out_dir(&d, pdf), d.join("My Paper (2)"));
        std::fs::create_dir_all(d.join("My Paper (2)")).unwrap();
        std::fs::write(d.join("My Paper (2)/meta.json"), r#"{"source": {"name": "My Paper.pdf"}}"#).unwrap();
        assert_eq!(out_dir(&d, pdf), d.join("My Paper (2)")); // an earlier conversion of it
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn progress_events() {
        let ev: Value = serde_json::from_str(
            r#"{"event":"progress","stage":"converting","batch":2,"batches":5,"pages":[11,20],"done_pages":10,"total_pages":47}"#,
        )
        .unwrap();
        match progress(&ev) {
            Some(Phase::Running { text, done, total }) => {
                assert_eq!(text, "Pages 11-20 (batch 2 of 5)");
                assert_eq!((done, total), (10, 47));
            }
            _ => panic!("not running"),
        }
        assert!(progress(&serde_json::json!({"event": "done"})).is_none());
    }

    /// The panel's code path end to end. Needs marker-pdf (skipped otherwise); about 30 s.
    fn marker_python() -> Option<PathBuf> {
        let py = crate::config::Config::load().python_path();
        let ok = std::process::Command::new(&py)
            .args(["-c", "import marker"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success());
        ok.then_some(py)
    }

    fn wait(state: &Arc<Mutex<State>>, secs: u64) -> Phase {
        let t = Instant::now();
        while state.lock().unwrap().running() && t.elapsed() < Duration::from_secs(secs) {
            std::thread::sleep(Duration::from_millis(200));
        }
        state.lock().unwrap().phase.clone()
    }

    #[test]
    fn converts_and_cancels_with_marker() {
        let Some(py) = marker_python() else {
            eprintln!("marker-pdf not installed, skipped");
            return;
        };
        let sample = Path::new(env!("CARGO_MANIFEST_DIR")).join("examples/papers/sample.pdf");
        let d = tmp("convert");
        std::env::set_var("FORMULA_SNIP_CACHE", d.join("cache"));

        // cancel right away
        let state = Arc::new(Mutex::new(State::default()));
        start(&py, &sample, &d.join("a"), "", state.clone(), egui::Context::default()).unwrap();
        cancel(&state);
        assert!(matches!(wait(&state, 120), Phase::Cancelled));

        // too many pages for the panel
        let state = Arc::new(Mutex::new(State::default()));
        start(&py, &sample, &d.join("b"), "1-200", state.clone(), egui::Context::default()).unwrap();
        match wait(&state, 120) {
            Phase::Failed(msg) => assert!(msg.contains("beyond the last page"), "{msg}"),
            _ => panic!("expected a failure"),
        }

        // a real conversion
        let state = Arc::new(Mutex::new(State::default()));
        let out = out_dir(&d, &sample);
        start(&py, &sample, &out, "", state.clone(), egui::Context::default()).unwrap();
        match wait(&state, 600) {
            Phase::Done { out: o, summary, .. } => {
                assert_eq!(o, out.canonicalize().unwrap()); // /var -> /private/var on macOS
                assert!(summary[0].starts_with("30 formulas (6 display"), "{summary:?}");
                assert!(out.join("paper.md").is_file());
                assert!(out.join("formulas.py").is_file());
            }
            Phase::Failed(m) => panic!("failed: {m}"),
            _ => panic!("did not finish"),
        }
        let _ = std::fs::remove_dir_all(&d);
    }
}
