# Formula Snip installer for Windows (PowerShell).
# Installs what's missing (Rust, Python, pipx, marker-pdf, llama.cpp), builds the app and installs it.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Say($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") + ";$env:USERPROFILE\.cargo\bin;$env:USERPROFILE\.local\bin" }

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  Say "Installing Rust (needs the Visual Studio C++ Build Tools; rustup will offer to install them)"
  winget install --id Rustlang.Rustup -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Say "Installing Python 3.12"
  winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
  Say "Installing pipx"
  python -m pip install --user pipx
  python -m pipx ensurepath
  Refresh-Path
}
if (-not ((pipx list --short) -match "^marker-pdf ")) {
  Say "Installing marker-pdf (downloads PyTorch, takes a few minutes)"
  pipx install marker-pdf
}

if (-not (Get-Command llama-server -ErrorAction SilentlyContinue)) {
  Say "Installing llama.cpp (runs marker's OCR model)"
  winget install --id ggml.llamacpp -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
}

Say "Building formula-snip.exe"
cargo build --release
$dest = "$env:LOCALAPPDATA\Programs\FormulaSnip"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Get-Process formula-snip -ErrorAction SilentlyContinue | Stop-Process
Copy-Item target\release\formula-snip.exe $dest -Force

$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Formula Snip.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "$dest\formula-snip.exe"; $s.Arguments = "--show"; $s.Save()

Say "Testing OCR on examples\gaussian_integral.png"
& "$dest\formula-snip.exe" --image examples\gaussian_integral.png | Write-Host

Start-Process "$dest\formula-snip.exe" -ArgumentList "--show"
Say "Installed to $dest. Find the fx icon in the system tray and set your shortcut under Settings."
