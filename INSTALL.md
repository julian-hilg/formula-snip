# Installing Formula Snip

## Requirements

| | |
|---|---|
| OS | macOS 11+, Windows 10/11, or Linux (X11 for the global shortcut) |
| Disk | ~3 GB for `marker-pdf` + the OCR model (downloaded once) |
| Tools | Rust, Python 3.10+ with pipx, `marker-pdf`, `llama.cpp` (`llama-server`). **The installers set these up for you.** |

## One-command install

**macOS / Linux**

```bash
git clone https://github.com/julian-hilg/formula-snip.git && cd formula-snip && ./install.sh
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/julian-hilg/formula-snip.git; cd formula-snip; .\install.ps1
```

What the installer does:

1. **Linux only:** installs the GTK / tray libraries with `apt` if they're missing.
2. Installs **Rust** (rustup) if `cargo` is missing.
3. Installs **pipx**, plus Python on Windows, if missing.
4. Installs **marker-pdf** with `pipx install marker-pdf`, which provides the local OCR model, and **llama.cpp**, whose `llama-server` runs it (`brew install llama.cpp`, or `winget install ggml.llamacpp` on Windows). It also adds `antlr4-python3-runtime` 4.11 to marker's environment: sympy's LaTeX parser needs it for the `formulas.py` that `formula-snip convert` writes.
5. Builds and installs the app:
   - macOS: `/Applications/FormulaSnip.app`
   - Linux: `~/.local/bin/formula-snip` and an app-menu entry
   - Windows: `%LOCALAPPDATA%\Programs\FormulaSnip` and a Start-menu entry
6. Runs one test snip on `examples/gaussian_integral.png`. On a new machine this downloads the model weights (1–2 min). It should print
   `\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}`
7. Starts the app.

## After installing

1. Open the panel from the **ƒx** icon and set your shortcut under **Settings → Set shortcut …**.
2. **macOS:** on the first snip, allow **Screen Recording**, then quit (ƒx → Quit) and reopen.
3. Optional, start at login:
   - macOS: System Settings → General → Login Items → add *FormulaSnip*
   - Windows: put a shortcut to `formula-snip.exe` in `shell:startup`
   - Linux: copy `~/.local/share/applications/formula-snip.desktop` to `~/.config/autostart/`

## Install with a coding agent

Paste this into your coding agent on the target computer:

> Please clone `https://github.com/julian-hilg/formula-snip.git` and install it. On macOS or Linux run `./install.sh`; on Windows run `.\install.ps1` in PowerShell. If a step fails, fix the cause (for example missing Rust, Python, pipx, build tools, `marker-pdf` or `llama.cpp`) and run the installer again until it finishes. Then check that `formula-snip --image examples/gaussian_integral.png` prints `\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}`. Finally, tell me which permissions or settings I still need to set by hand (shortcut, Screen Recording on macOS).

## Manual install

```bash
pipx install marker-pdf             # OCR model
pipx inject marker-pdf "antlr4-python3-runtime==4.11.*"   # for formula-snip convert → formulas.py
brew install llama.cpp              # runs the model (Windows: winget install ggml.llamacpp)
cargo build --release               # app
./target/release/formula-snip --show
```

If `marker-pdf` lives somewhere other than the pipx default, set the Python path in *Settings*, or set `"python"` in `config.json`.

## Updating / uninstalling

```bash
git pull && ./install.sh            # update (Windows: .\install.ps1)
```

To uninstall, delete the app (see step 5 above) and its settings folder (see *Configuration* in the README). `pipx uninstall marker-pdf` also removes the OCR model.
