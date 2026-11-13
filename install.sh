#!/usr/bin/env bash
# Formula Snip installer for macOS and Linux.
# Installs what's missing (Rust, pipx, marker-pdf, llama.cpp), builds the app and installs it.
set -euo pipefail
cd "$(dirname "$0")"
say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
OS=$(uname)

# 1. Linux system libraries (tray icon + GTK)
if [[ $OS == Linux ]] && command -v apt-get >/dev/null && ! pkg-config --exists gtk+-3.0 2>/dev/null; then
  say "Installing GTK / tray libraries (sudo)"
  sudo apt-get update && sudo apt-get install -y build-essential pkg-config libgtk-3-dev libxdo-dev libayatana-appindicator3-dev
fi

# 2. Rust
if ! command -v cargo >/dev/null; then
  [[ -x "$HOME/.cargo/bin/cargo" ]] || { say "Installing Rust"; curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; }
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# 3. pipx + marker-pdf (the local OCR model)
if ! command -v pipx >/dev/null; then
  say "Installing pipx"
  if [[ $OS == Darwin ]] && command -v brew >/dev/null; then brew install pipx
  elif command -v apt-get >/dev/null; then sudo apt-get install -y pipx
  else python3 -m pip install --user pipx; fi
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! pipx list --short 2>/dev/null | grep -q '^marker-pdf '; then
  say "Installing marker-pdf (downloads PyTorch, takes a few minutes)"
  pipx install marker-pdf
fi
# sympy's LaTeX parser (used by `formula-snip convert` for formulas.py) needs this runtime
if ! pipx runpip marker-pdf show antlr4-python3-runtime >/dev/null 2>&1; then
  pipx inject marker-pdf "antlr4-python3-runtime==4.11.*"
fi

# 4. llama.cpp (marker's OCR model runs on llama-server)
if ! command -v llama-server >/dev/null; then
  if command -v brew >/dev/null; then
    say "Installing llama.cpp"
    brew install llama.cpp
  else
    echo "llama-server not found. Install llama.cpp: https://github.com/ggml-org/llama.cpp/releases"
    echo "(put llama-server on your PATH), then run ./install.sh again."
    exit 1
  fi
fi

# 5. Build + install
if [[ $OS == Darwin ]]; then
  say "Building Formula Snip.app"
  scripts/bundle-macos.sh
  DEST=/Applications; [[ -w $DEST ]] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
  pkill -x formula-snip 2>/dev/null || true
  rm -rf "$DEST/FormulaSnip.app"; cp -R target/FormulaSnip.app "$DEST/"
  BIN="$DEST/FormulaSnip.app/Contents/MacOS/formula-snip"
else
  say "Building formula-snip"
  cargo build --release
  mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons"
  install -m 755 target/release/formula-snip "$HOME/.local/bin/formula-snip"
  cp assets/icon.png "$HOME/.local/share/icons/formula-snip.png"
  cat > "$HOME/.local/share/applications/formula-snip.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Formula Snip
Comment=Snip a formula, get LaTeX
Exec=$HOME/.local/bin/formula-snip --show
Icon=formula-snip
Categories=Utility;Education;
DESKTOP
  BIN="$HOME/.local/bin/formula-snip"
fi

# 6. Check the OCR end-to-end (first run downloads the model weights, ~1-2 min)
say "Testing OCR on examples/gaussian_integral.png"
"$BIN" --image examples/gaussian_integral.png

say "Installed: $BIN"
if [[ $OS == Darwin ]]; then open "$DEST/FormulaSnip.app"; else nohup "$BIN" --show >/dev/null 2>&1 & fi
echo "Open the panel from the ƒx icon in the menu bar / system tray and set your shortcut under Settings."
