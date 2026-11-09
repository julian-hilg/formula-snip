//! Formula Snip — snip a formula anywhere on screen, get LaTeX in your clipboard.
//! Fully local: OCR runs through marker's surya model in a background Python helper.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app;
mod backend;
mod capture;
mod config;
mod hotkey;
mod reopen;

use eframe::egui;
use std::path::PathBuf;

const USAGE: &str = "formula-snip            start the tray app
formula-snip --show     start with the panel open
formula-snip FILE...    start and recognise these images
formula-snip --image FILE...   print LaTeX for images and exit (no GUI)";

fn main() -> eframe::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        return Ok(());
    }
    if args.first().map(String::as_str) == Some("--image") {
        std::process::exit(cli(&args[1..]));
    }

    // Already running? Show that instance's panel instead of starting a second one.
    if reopen::signal_running_instance() {
        return Ok(());
    }

    let first_run = !dirs::config_dir().unwrap_or_default().join("formula-snip/config.json").exists();
    let files: Vec<PathBuf> = args.iter().filter(|a| !a.starts_with("--")).map(PathBuf::from).collect();
    let visible = first_run || !files.is_empty() || args.iter().any(|a| a == "--show");
    if first_run {
        config::Config::load().save(); // write defaults so users can find the file
    }

    let icon = eframe::icon_data::from_png_bytes(include_bytes!("../assets/icon.png")).expect("icon");
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Formula Snip")
            .with_app_id("formula-snip")
            .with_inner_size([460.0, 560.0])
            .with_min_inner_size([360.0, 320.0])
            .with_always_on_top()
            .with_visible(visible)
            .with_icon(icon),
        ..Default::default()
    };
    eframe::run_native("Formula Snip", options, Box::new(move |cc| Ok(Box::new(app::App::new(cc, files)))))
}

fn cli(files: &[String]) -> i32 {
    let cfg = config::Config::load();
    let mut backend = match backend::Backend::start(&cfg.python_path()) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {e:#}");
            return 1;
        }
    };
    let mut code = 0;
    for f in files {
        let path = std::fs::canonicalize(f).unwrap_or_else(|_| PathBuf::from(f));
        match backend.recognize(&path) {
            Ok(latex) => println!("{latex}"),
            Err(e) => {
                eprintln!("{f}: {e:#}");
                code = 1;
            }
        }
    }
    code
}
