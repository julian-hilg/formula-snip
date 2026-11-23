//! Interactive region screenshots: native selection tools on macOS/Linux,
//! an embedded Python selector on Windows.
//! Returns `Ok(None)` when the user cancels.

use anyhow::Result;
use std::path::{Path, PathBuf};
use std::process::Command;

pub fn snip_region() -> Result<Option<PathBuf>> {
    let path = std::env::temp_dir().join(format!("formula-snip-{}.png", std::process::id()));
    let _ = std::fs::remove_file(&path);
    platform_capture(&path)?;
    let ok = std::fs::metadata(&path).map(|m| m.len() > 0).unwrap_or(false);
    Ok(ok.then_some(path))
}

#[cfg(target_os = "macos")]
fn platform_capture(path: &Path) -> Result<()> {
    // -i: drag a region (Esc cancels), -x: no shutter sound
    Command::new("/usr/sbin/screencapture").args(["-i", "-x"]).arg(path).status()?;
    Ok(())
}

#[cfg(target_os = "linux")]
fn platform_capture(path: &Path) -> Result<()> {
    let p = path.to_string_lossy();
    // First tool that exists wins: GNOME, KDE, wlroots (Sway/Hyprland), X11, Flameshot.
    let tools: [(&str, String); 5] = [
        ("gnome-screenshot", format!("gnome-screenshot -a -f '{p}'")),
        ("spectacle", format!("spectacle -r -b -n -o '{p}'")),
        ("slurp", format!("grim -g \"$(slurp)\" '{p}'")),
        ("maim", format!("maim -s '{p}'")),
        ("flameshot", format!("flameshot gui -r > '{p}'")),
    ];
    for (bin, cmd) in tools {
        let found = Command::new("sh").arg("-c").arg(format!("command -v {bin}")).output()?.status.success();
        if found {
            Command::new("sh").arg("-c").arg(cmd).status()?;
            return Ok(());
        }
    }
    anyhow::bail!("no screenshot tool found — install gnome-screenshot, spectacle, grim+slurp, maim or flameshot")
}

#[cfg(target_os = "windows")]
fn platform_capture(path: &Path) -> Result<()> {
    use std::os::windows::process::CommandExt;
    let script = crate::config::app_dir(dirs::data_local_dir()).join("capture_windows.py");
    std::fs::write(&script, include_str!("../backend/capture_windows.py"))?;
    let output = Command::new(crate::config::Config::load().python_path())
        .arg(&script)
        .arg(path)
        .creation_flags(0x0800_0000)
        .output()?;
    anyhow::ensure!(
        output.status.success(),
        "screen selection failed (Python needs tkinter and Pillow): {}",
        String::from_utf8_lossy(&output.stderr)
    );
    Ok(())
}
