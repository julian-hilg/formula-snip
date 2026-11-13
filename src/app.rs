//! The panel UI (egui), the tray icon, the global shortcut and the background worker.

use crate::{backend::Backend, capture, config::Config, hotkey, paper};
use eframe::egui::{self, Color32, ColorImage, RichText, TextureHandle, ViewportCommand};
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use tray_icon::menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem};

/// Only the latest snip is kept (no history).
const KEEP: usize = 1;

// ---------------------------------------------------------------- shared state

#[derive(Clone)]
enum Status {
    Recognizing,
    Done,
    Failed(String),
}

#[derive(Clone)]
struct Entry {
    id: u64,
    image: Arc<ColorImage>,
    latex: String,
    status: Status,
    secs: f32,
}

#[derive(Clone, PartialEq)]
enum Ocr {
    Starting,
    Ready,
    Failed(String),
}

#[derive(Default)]
struct Shared {
    entries: Vec<Entry>, // the current snip (newest first)
    ocr: Option<Ocr>,
    selected: Option<u64>,
}

/// Busy/cancel flags shared by the worker, the panel and the tray menu.
#[derive(Clone, Default)]
struct Flags {
    busy: Arc<AtomicBool>,
    cancel: Arc<AtomicBool>,
}

impl Flags {
    /// Cancel the snip that is being recognised (its result is thrown away).
    fn cancel(&self) {
        if self.busy.load(Ordering::Relaxed) {
            self.cancel.store(true, Ordering::Relaxed);
        }
    }
}

enum Job {
    Snip,
    File(PathBuf),
    Restart(PathBuf),
}

// ---------------------------------------------------------------- worker thread

fn worker(rx: Receiver<Job>, shared: Arc<Mutex<Shared>>, ctx: egui::Context, show_after: Arc<AtomicBool>, flags: Flags, python: PathBuf) {
    let set_ocr = |s: Ocr| {
        shared.lock().unwrap().ocr = Some(s);
        ctx.request_repaint();
    };
    let start = |python: &PathBuf| {
        set_ocr(Ocr::Starting);
        match Backend::start(python) {
            Ok(b) => {
                set_ocr(Ocr::Ready);
                Some(b)
            }
            Err(e) => {
                set_ocr(Ocr::Failed(format!("{e:#}")));
                None
            }
        }
    };
    let mut backend = start(&python);
    let mut clipboard = arboard::Clipboard::new().ok(); // kept alive: Linux clipboards need an owner
    let mut next_id = 0u64;

    while let Ok(job) = rx.recv() {
        let (path, temporary) = match job {
            Job::Restart(py) => {
                drop(backend.take()); // stop the old helper first
                backend = start(&py);
                continue;
            }
            Job::File(p) => (p, false),
            Job::Snip => {
                let r = capture::snip_region();
                while rx.try_recv().is_ok() {} // drop shortcut presses made while selecting
                match r {
                    Ok(Some(p)) => (p, true),
                    Ok(None) => continue, // cancelled
                    Err(e) => {
                        set_ocr(Ocr::Failed(format!("screenshot failed: {e:#}")));
                        continue;
                    }
                }
            }
        };

        let Ok(img) = image::open(&path).map(|i| i.to_rgba8()) else { continue };
        let color = ColorImage::from_rgba_unmultiplied([img.width() as usize, img.height() as usize], img.as_raw());
        next_id += 1;
        let id = next_id;
        {
            let mut s = shared.lock().unwrap();
            s.entries.insert(0, Entry { id, image: Arc::new(color), latex: String::new(), status: Status::Recognizing, secs: 0.0 });
            s.entries.truncate(KEEP);
            s.selected = Some(id);
        }
        if show_after.load(Ordering::Relaxed) {
            show_panel(&ctx);
        }
        ctx.request_repaint();

        flags.cancel.store(false, Ordering::Relaxed);
        flags.busy.store(true, Ordering::Relaxed);
        let t = Instant::now();
        let result = match backend.as_mut() {
            Some(b) => b.recognize(&path),
            None => Err(anyhow::anyhow!("OCR model is not running — check Settings → Python")),
        };
        if temporary {
            let _ = std::fs::remove_file(&path);
        }
        flags.busy.store(false, Ordering::Relaxed);
        let mut s = shared.lock().unwrap();
        if flags.cancel.swap(false, Ordering::Relaxed) {
            // Cancelled: forget this snip and anything still queued.
            s.entries.retain(|e| e.id != id);
            s.selected = s.entries.first().map(|e| e.id);
            while let Ok(job) = rx.try_recv() {
                if let Job::Restart(py) = job {
                    drop(backend.take());
                    backend = start(&py);
                }
            }
            ctx.request_repaint();
            continue;
        }
        if let Some(e) = s.entries.iter_mut().find(|e| e.id == id) {
            e.secs = t.elapsed().as_secs_f32();
            match result {
                Ok(latex) if !latex.is_empty() => {
                    if let Some(cb) = clipboard.as_mut() {
                        let _ = cb.set_text(latex.clone());
                    }
                    e.latex = latex;
                    e.status = Status::Done;
                }
                Ok(_) => e.status = Status::Failed("No text recognised".into()),
                Err(err) => e.status = Status::Failed(format!("{err:#}")),
            }
        }
        ctx.request_repaint();
    }
}

fn show_panel(ctx: &egui::Context) {
    ctx.send_viewport_cmd(ViewportCommand::Visible(true));
    ctx.send_viewport_cmd(ViewportCommand::Minimized(false));
    ctx.send_viewport_cmd(ViewportCommand::Focus);
    ctx.request_repaint();
}

// ---------------------------------------------------------------- tray icon

fn build_tray(tx: Sender<Job>, ctx: egui::Context, flags: Flags) {
    MenuEvent::set_event_handler(Some(move |e: MenuEvent| match e.id.0.as_str() {
        "snip" => {
            let _ = tx.send(Job::Snip);
        }
        "cancel" => {
            flags.cancel();
            ctx.request_repaint();
        }
        "show" => show_panel(&ctx),
        "quit" => std::process::exit(0), // the Python helper sees EOF on stdin and exits too
        _ => {}
    }));

    // Menus aren't thread-safe, so the menu is built on the thread that owns the tray
    // (the GTK thread on Linux, the main thread elsewhere).
    let make = || {
        let menu = Menu::new();
        let _ = menu.append_items(&[
            &MenuItem::with_id("snip", "New Snip", true, None),
            &MenuItem::with_id("cancel", "Cancel", true, None),
            &MenuItem::with_id("show", "Show Panel", true, None),
            &PredefinedMenuItem::separator(),
            &MenuItem::with_id("quit", "Quit Formula Snip", true, None),
        ]);
        let png = image::load_from_memory(include_bytes!("../assets/tray.png")).unwrap().to_rgba8();
        let icon = tray_icon::Icon::from_rgba(png.to_vec(), png.width(), png.height()).unwrap();
        tray_icon::TrayIconBuilder::new()
            .with_menu(Box::new(menu))
            .with_icon(icon)
            .with_icon_as_template(true)
            .with_tooltip("Formula Snip")
            .build()
            .expect("tray icon")
    };

    #[cfg(target_os = "linux")]
    std::thread::spawn(move || {
        gtk::init().expect("gtk");
        let _tray = make();
        gtk::main();
    });
    #[cfg(not(target_os = "linux"))]
    std::mem::forget(make()); // lives for the whole program
}

// ---------------------------------------------------------------- the app

#[derive(Clone, Copy, PartialEq)]
enum Tab {
    Snip,
    Paper,
}

pub struct App {
    shared: Arc<Mutex<Shared>>,
    tx: Sender<Job>,
    flags: Flags,
    config: Config,
    show_after: Arc<AtomicBool>,
    hotkeys: GlobalHotKeyManager,
    hotkey_id: Arc<AtomicU32>,
    hotkey_error: Option<String>,
    recording: bool,
    textures: HashMap<u64, TextureHandle>,
    copied: Option<(&'static str, Instant)>,
    tab: Tab,
    paper: Arc<Mutex<paper::State>>,
    paper_pdf: Option<PathBuf>,
    paper_pages: String,
    paper_error: Option<String>,
}

impl App {
    pub fn new(cc: &eframe::CreationContext, open: Vec<PathBuf>) -> Self {
        let ctx = cc.egui_ctx.clone();
        let config = Config::load();
        let shared = Arc::new(Mutex::new(Shared::default()));
        let show_after = Arc::new(AtomicBool::new(config.show_panel_after_snip));
        let (tx, rx) = channel();
        let flags = Flags::default();
        {
            let (shared, ctx, show_after, flags, python) = (shared.clone(), ctx.clone(), show_after.clone(), flags.clone(), config.python_path());
            std::thread::spawn(move || worker(rx, shared, ctx, show_after, flags, python));
        }
        let mut first_pdf = None;
        for p in open {
            if is_pdf(&p) {
                first_pdf.get_or_insert(p);
            } else {
                let _ = tx.send(Job::File(p));
            }
        }
        build_tray(tx.clone(), ctx.clone(), flags.clone());
        {
            let ctx = ctx.clone();
            crate::reopen::listen(move || show_panel(&ctx));
        }

        let hotkey_id = Arc::new(AtomicU32::new(0));
        {
            let (tx, id) = (tx.clone(), hotkey_id.clone());
            GlobalHotKeyEvent::set_event_handler(Some(move |e: GlobalHotKeyEvent| {
                if e.state == HotKeyState::Pressed && e.id == id.load(Ordering::Relaxed) {
                    let _ = tx.send(Job::Snip);
                }
            }));
        }
        let mut app = Self {
            shared,
            tx,
            flags,
            config,
            show_after,
            hotkeys: GlobalHotKeyManager::new().expect("global shortcut support"),
            hotkey_id,
            hotkey_error: None,
            recording: false,
            textures: HashMap::new(),
            copied: None,
            tab: if first_pdf.is_some() { Tab::Paper } else { Tab::Snip },
            paper: Arc::new(Mutex::new(paper::State::default())),
            paper_pdf: first_pdf,
            paper_pages: String::new(),
            paper_error: None,
        };
        app.register_hotkey();
        app
    }

    fn register_hotkey(&mut self) {
        self.hotkey_error = None;
        if self.config.hotkey.trim().is_empty() {
            return; // no shortcut chosen yet
        }
        match hotkey::parse(&self.config.hotkey) {
            Some(hk) => match self.hotkeys.register(hk) {
                Ok(()) => self.hotkey_id.store(hk.id(), Ordering::Relaxed),
                Err(e) => self.hotkey_error = Some(format!("Shortcut unavailable (used by another app?): {e}")),
            },
            None => self.hotkey_error = Some(format!("Invalid shortcut \"{}\"", self.config.hotkey)),
        }
    }

    fn unregister_hotkey(&mut self) {
        if let Some(hk) = hotkey::parse(&self.config.hotkey) {
            let _ = self.hotkeys.unregister(hk);
        }
        self.hotkey_id.store(0, Ordering::Relaxed);
    }

    fn record_shortcut(&mut self, ctx: &egui::Context) {
        let events = ctx.input(|i| i.events.clone());
        for ev in events {
            if let egui::Event::Key { key, physical_key, pressed: true, modifiers, .. } = ev {
                let key = physical_key.unwrap_or(key);
                if key == egui::Key::Escape {
                    self.recording = false;
                    self.register_hotkey();
                } else if let Some(s) = hotkey::from_press(key, modifiers) {
                    self.config.hotkey = s;
                    self.config.save();
                    self.recording = false;
                    self.register_hotkey();
                }
            }
        }
    }

    fn copy_button(&mut self, ui: &mut egui::Ui, label: &'static str, text: String) {
        let done = matches!(self.copied, Some((l, t)) if l == label && t.elapsed().as_secs_f32() < 1.2);
        if ui.button(if done { "Copied" } else { label }).clicked() {
            ui.ctx().copy_text(text);
            self.copied = Some((label, Instant::now()));
        }
        if done {
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(300));
        }
    }

    /// The Paper tab: PDF -> Markdown + formula registry, via `formula-snip convert`.
    fn paper_tab(&mut self, ui: &mut egui::Ui) {
        let phase = self.paper.lock().unwrap().phase.clone();
        let running = matches!(phase, paper::Phase::Running { .. } | paper::Phase::Cancelling);

        if !running {
            let name = self.paper_pdf.as_ref().and_then(|p| p.file_name()).map(|n| n.to_string_lossy().into_owned());
            let title = name.clone().unwrap_or_else(|| "Drop a PDF here".into());
            let sub = format!("{} up to {} pages, converted locally", if name.is_some() { "Ready to convert," } else { "or choose one," }, paper::MAX_PAGES);
            drop_zone(ui, 90.0, &title, &sub);
            ui.add_space(6.0);
            egui::Grid::new("paper_form").num_columns(2).spacing([8.0, 6.0]).show(ui, |ui| {
                ui.label("PDF:");
                ui.horizontal(|ui| {
                    if ui.button("Choose PDF …").clicked() {
                        if let Some(p) = rfd::FileDialog::new().add_filter("PDF", &["pdf", "PDF"]).pick_file() {
                            self.paper_pdf = Some(p);
                            self.paper_error = None;
                        }
                    }
                    if let Some(p) = &self.paper_pdf {
                        ui.add(egui::Label::new(RichText::new(tilde(p)).weak()).truncate()).on_hover_text(p.display().to_string());
                    }
                });
                ui.end_row();
                ui.label("Pages:");
                ui.horizontal(|ui| {
                    ui.add(egui::TextEdit::singleline(&mut self.paper_pages).hint_text("all").desired_width(90.0));
                    ui.weak("e.g. 1-12 or 1,3,5-7");
                });
                ui.end_row();
                ui.label("Save to:");
                ui.horizontal(|ui| {
                    if ui.button("Change …").clicked() {
                        if let Some(d) = rfd::FileDialog::new().set_directory(self.config.papers_dir()).pick_folder() {
                            self.config.papers_dir = d.display().to_string();
                            self.config.save();
                        }
                    }
                    if !self.config.papers_dir.is_empty() && ui.button("Downloads").on_hover_text("Back to the default").clicked() {
                        self.config.papers_dir.clear();
                        self.config.save();
                    }
                    let dir = self.config.papers_dir();
                    ui.add(egui::Label::new(RichText::new(tilde(&dir)).weak()).truncate()).on_hover_text(dir.display().to_string());
                });
                ui.end_row();
            });
            ui.add_space(6.0);
            let can = self.paper_pdf.is_some();
            if ui.add_enabled(can, egui::Button::new("Convert")).clicked() {
                if let Some(pdf) = self.paper_pdf.clone() {
                    let dir = self.config.papers_dir();
                    let out = paper::out_dir(&dir, &pdf);
                    let started = std::fs::create_dir_all(&dir).map_err(anyhow::Error::from).and_then(|_| {
                        paper::start(&self.config.python_path(), &pdf, &out, &self.paper_pages, self.paper.clone(), ui.ctx().clone())
                    });
                    self.paper_error = started.err().map(|e| format!("{e:#}"));
                }
            }
        }

        ui.add_space(6.0);
        match phase {
            paper::Phase::Idle => {}
            paper::Phase::Running { text, done, total } => {
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(text);
                });
                if total > 0 {
                    ui.add(egui::ProgressBar::new(done as f32 / total as f32).text(format!("{done} of {total} pages")));
                }
                if ui.button("Cancel").on_hover_text("Finished batches are kept: converting again resumes").clicked() {
                    paper::cancel(&self.paper);
                }
            }
            paper::Phase::Cancelling => {
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label("Stopping …");
                });
            }
            paper::Phase::Done { out, summary, secs } => {
                ui.label(RichText::new(format!("Done in {secs:.0} s")).strong());
                for line in &summary {
                    ui.label(line);
                }
                ui.add(egui::Label::new(RichText::new(tilde(&out)).weak()).truncate()).on_hover_text(out.display().to_string());
                ui.horizontal(|ui| {
                    if ui.button("Open folder").clicked() {
                        paper::open(&out);
                    }
                    if ui.button("Open paper.md").clicked() {
                        paper::open(&out.join("paper.md"));
                    }
                    self.copy_button(ui, "Copy path", out.display().to_string());
                });
            }
            paper::Phase::Failed(msg) => {
                ui.colored_label(Color32::RED, msg);
                ui.weak(format!("Log: {}", tilde(&paper::log_path())));
            }
            paper::Phase::Cancelled => {
                ui.weak("Cancelled. Finished batches are kept, so converting again continues where it stopped.");
            }
        }
        if let Some(err) = &self.paper_error {
            ui.colored_label(Color32::RED, err);
        }
        ui.add_space(4.0);
        ui.weak(format!(
            "Writes paper.md, images, formulas.json, variables.json and formulas.py into a folder named after the PDF. \
             The panel takes up to {} pages per PDF; the command line (formula-snip convert) has no limit.",
            paper::MAX_PAGES
        ));
    }

    fn texture(&mut self, ctx: &egui::Context, e: &Entry) -> TextureHandle {
        self.textures
            .entry(e.id)
            .or_insert_with(|| ctx.load_texture(format!("snip{}", e.id), (*e.image).clone(), Default::default()))
            .clone()
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Closing the window only hides it; quit from the tray menu.
        if ctx.input(|i| i.viewport().close_requested()) {
            ctx.send_viewport_cmd(ViewportCommand::CancelClose);
            ctx.send_viewport_cmd(ViewportCommand::Visible(false));
        }
        for f in ctx.input(|i| i.raw.dropped_files.clone()) {
            if let Some(p) = f.path {
                if is_pdf(&p) {
                    self.paper_pdf = Some(p);
                    self.paper_error = None;
                    self.tab = Tab::Paper;
                } else {
                    let _ = self.tx.send(Job::File(p));
                    self.tab = Tab::Snip;
                }
            }
        }
        if self.recording {
            self.record_shortcut(ctx);
        }

        // Copy what we draw out of the lock (images are Arc'd, so this is cheap).
        let (entries, ocr, sel) = {
            let s = self.shared.lock().unwrap();
            (s.entries.clone(), s.ocr.clone().unwrap_or(Ocr::Starting), s.selected)
        };
        let selected = sel.and_then(|id| entries.iter().find(|e| e.id == id)).or(entries.first());
        self.textures.retain(|id, _| entries.iter().any(|e| e.id == *id)); // free old images
        let python_hint = format!("auto: {}", tilde(&self.config.python_path()));

        egui::CentralPanel::default().show(ctx, |ui| {
            // header
            ui.horizontal(|ui| {
                ui.heading(RichText::new("ƒx").italics().strong());
                ui.heading("Formula Snip");
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let (color, text) = match &ocr {
                        Ocr::Ready => (Color32::from_rgb(34, 160, 80), "Ready"),
                        Ocr::Starting => (Color32::from_rgb(230, 160, 0), "Loading OCR model …"),
                        Ocr::Failed(_) => (Color32::RED, "OCR error"),
                    };
                    ui.colored_label(color, text);
                    let (r, _) = ui.allocate_exact_size(egui::vec2(10.0, 10.0), egui::Sense::hover());
                    ui.painter().circle_filled(r.center(), 4.5, color);
                });
            });
            if let Ocr::Failed(msg) = &ocr {
                ui.colored_label(Color32::RED, msg);
            }
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.tab, Tab::Snip, "Snip");
                ui.selectable_value(&mut self.tab, Tab::Paper, "Paper");
            });
            ui.separator();
            if self.tab == Tab::Paper {
                self.paper_tab(ui);
                return;
            }
            ui.horizontal(|ui| {
                let can = ocr == Ocr::Ready;
                let busy = self.flags.busy.load(Ordering::Relaxed);
                if ui.add_enabled(can && !busy, egui::Button::new("New Snip")).clicked() {
                    ctx.send_viewport_cmd(ViewportCommand::Visible(false));
                    let _ = self.tx.send(Job::Snip);
                }
                if ui.add_enabled(busy, egui::Button::new("Cancel")).on_hover_text("Stop the current snip").clicked() {
                    self.flags.cancel();
                }
            });
            ui.separator();

            // current snip
            match selected {
                None => drop_zone(ui, 150.0, "Drop an image of a formula here", "or click New Snip and drag a box around it"),
                Some(e) => {
                    let tex = self.texture(ctx, e);
                    egui::Frame::none().fill(Color32::WHITE).rounding(6.0).inner_margin(8.0).show(ui, |ui| {
                        ui.set_width(ui.available_width());
                        let size = tex.size_vec2();
                        let scale = (ui.available_width() / size.x).min(160.0 / size.y).min(1.0);
                        ui.vertical_centered(|ui| ui.image((tex.id(), size * scale)));
                    });
                    ui.add_space(6.0);
                    match &e.status {
                        Status::Recognizing => {
                            ui.horizontal(|ui| {
                                ui.spinner();
                                ui.label("Recognising …");
                            });
                        }
                        Status::Failed(msg) => {
                            ui.colored_label(Color32::RED, msg);
                        }
                        Status::Done => {
                            let latex = e.latex.clone();
                            egui::ScrollArea::vertical().id_salt("latex").max_height(140.0).show(ui, |ui| {
                                ui.add(egui::TextEdit::multiline(&mut latex.as_str()).code_editor().desired_width(f32::INFINITY).desired_rows(3));
                            });
                            let secs = e.secs;
                            ui.horizontal(|ui| {
                                self.copy_button(ui, "Copy LaTeX", latex.clone());
                                self.copy_button(ui, "$…$", format!("${latex}$"));
                                self.copy_button(ui, "\\[…\\]", format!("\\[\n{latex}\n\\]"));
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| ui.weak(format!("{secs:.1} s")));
                            });
                        }
                    }
                }
            }

            if !entries.is_empty() {
                ui.add_space(6.0);
                drop_zone(ui, 44.0, "Drop an image here", "");
            }

            // settings
            ui.add_space(6.0);
            egui::CollapsingHeader::new("Settings").default_open(self.config.hotkey.is_empty()).show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label("Shortcut:");
                    if self.recording {
                        ui.colored_label(Color32::from_rgb(37, 99, 235), "Press the new shortcut … (Esc cancels)");
                    } else {
                        if self.config.hotkey.is_empty() {
                            ui.weak("none yet");
                        } else {
                            ui.monospace(hotkey::pretty(&self.config.hotkey));
                        }
                        let label = if self.config.hotkey.is_empty() { "Set shortcut …" } else { "Change …" };
                        if ui.button(label).clicked() {
                            self.unregister_hotkey();
                            self.recording = true;
                        }
                    }
                });
                if let Some(err) = &self.hotkey_error {
                    ui.colored_label(Color32::RED, err);
                }
                ui.horizontal(|ui| {
                    ui.label("Python:");
                    ui.add(egui::TextEdit::singleline(&mut self.config.python).hint_text(python_hint.as_str()).desired_width(220.0));
                    if ui.button("Restart OCR").clicked() {
                        self.config.save();
                        let _ = self.tx.send(Job::Restart(self.config.python_path()));
                    }
                });
                if ui.checkbox(&mut self.config.show_panel_after_snip, "Show this panel after each snip").changed() {
                    self.show_after.store(self.config.show_panel_after_snip, Ordering::Relaxed);
                    self.config.save();
                }
                ui.weak(format!("OCR log: {}", tilde(&crate::backend::log_path())));
            });
        });
    }
}

fn is_pdf(p: &std::path::Path) -> bool {
    p.extension().is_some_and(|e| e.eq_ignore_ascii_case("pdf"))
}

/// Show paths with `~` instead of the home folder.
pub fn tilde(p: &std::path::Path) -> String {
    let s = p.display().to_string();
    match dirs::home_dir() {
        Some(h) if s.starts_with(&*h.to_string_lossy()) => format!("~{}", &s[h.to_string_lossy().len()..]),
        _ => s,
    }
}

/// A dashed box that lights up while files are dragged over the window.
fn drop_zone(ui: &mut egui::Ui, height: f32, title: &str, subtitle: &str) {
    let hovering = ui.ctx().input(|i| !i.raw.hovered_files.is_empty());
    let (rect, _) = ui.allocate_exact_size(egui::vec2(ui.available_width(), height), egui::Sense::hover());
    let accent = Color32::from_rgb(37, 99, 235);
    let color = if hovering { accent } else { ui.visuals().weak_text_color() };
    if hovering {
        ui.painter().rect_filled(rect, 8.0, accent.gamma_multiply(0.08));
    }
    let r = rect.shrink(1.0);
    let corners = [r.left_top(), r.right_top(), r.right_bottom(), r.left_bottom(), r.left_top()];
    ui.painter().extend(egui::Shape::dashed_line(&corners, egui::Stroke::new(1.5_f32, color), 7.0, 5.0));
    let title_size = if subtitle.is_empty() { 13.0 } else { 15.0 };
    let title_pos = if subtitle.is_empty() { rect.center() } else { rect.center() - egui::vec2(0.0, 10.0) };
    ui.painter().text(title_pos, egui::Align2::CENTER_CENTER, title, egui::FontId::proportional(title_size), color);
    if !subtitle.is_empty() {
        ui.painter().text(rect.center() + egui::vec2(0.0, 14.0), egui::Align2::CENTER_CENTER, subtitle, egui::FontId::proportional(12.0), ui.visuals().weak_text_color());
    }
}
