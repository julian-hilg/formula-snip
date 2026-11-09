//! Interactive region screenshot using each OS's own selection tool.
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
    // Windows' built-in Snipping overlay puts the region on the clipboard; wait for a new image.
    use std::time::{Duration, Instant};
    let mut cb = arboard::Clipboard::new()?;
    let fingerprint = |cb: &mut arboard::Clipboard| cb.get_image().ok().map(|i| (i.width, i.height, i.bytes.len(), i.bytes.iter().step_by(97).map(|b| *b as u64).sum::<u64>()));
    let before = fingerprint(&mut cb);
    Command::new("explorer").arg("ms-screenclip:").spawn()?;
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(60) {
        std::thread::sleep(Duration::from_millis(250));
        let now = fingerprint(&mut cb);
        if now.is_some() && now != before {
            let img = cb.get_image()?;
            image::RgbaImage::from_raw(img.width as u32, img.height as u32, img.bytes.into_owned())
                .ok_or_else(|| anyhow::anyhow!("bad clipboard image"))?
                .save(path)?;
            return Ok(());
        }
    }
    Ok(()) // timed out = cancelled
}
