#!/bin/bash
# Build target/FormulaSnip.app (menu-bar app, no Dock icon), ad-hoc signed.
set -euo pipefail
cd "$(dirname "$0")/.."
cargo build --release
APP=target/FormulaSnip.app
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp target/release/formula-snip "$APP/Contents/MacOS/"

ICONSET=$(mktemp -d)/icon.iconset; mkdir -p "$ICONSET"
for s in 16 32 64 128 256 512; do
  sips -z $s $s assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Formula Snip</string>
  <key>CFBundleIdentifier</key><string>io.github.formula-snip</string>
  <key>CFBundleExecutable</key><string>formula-snip</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1
echo "Built $APP"
