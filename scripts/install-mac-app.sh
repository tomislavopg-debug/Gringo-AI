#!/usr/bin/env bash
# ── Gringo AI – Mac-App installieren ─────────────────────────────────
# Legt "Gringo AI.app" (mit G-Logo) in den Programme-Ordner und ins Dock.
# Ein Klick auf die App startet Gringo AI.
#
# Ausführen (einmalig):   ./scripts/install-mac-app.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP="/Applications/Gringo AI.app"

echo "Installiere Gringo AI.app …"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REPO_ROOT/launcher/GringoAI.icns" "$APP/Contents/Resources/GringoAI.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Gringo AI</string>
  <key>CFBundleDisplayName</key><string>Gringo AI</string>
  <key>CFBundleIdentifier</key><string>de.gringo.gringo-ai</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>GringoAI</string>
  <key>CFBundleIconFile</key><string>GringoAI</string>
  <key>LSUIElement</key><true/>
  <key>LSArchitecturePriority</key>
  <array><string>arm64</string><string>x86_64</string></array>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST

START_CMD="$REPO_ROOT/scripts/gringo-start.command"
chmod +x "$START_CMD"

# Kleines natives Startprogramm (Apple-Chip) bauen, damit macOS nicht nach
# Rosetta fragt. Fallback: Shell-Skript.
TMP_C="$(mktemp -t gringo-launcher).c"
cat > "$TMP_C" <<CSRC
#include <unistd.h>
int main(void) {
  execl("/usr/bin/open", "open", "-a", "Terminal", "$START_CMD", (char *)0);
  return 1;
}
CSRC
if command -v clang &>/dev/null && clang -O2 -o "$APP/Contents/MacOS/GringoAI" "$TMP_C" 2>/dev/null; then
  echo "Natives Startprogramm gebaut."
else
  cat > "$APP/Contents/MacOS/GringoAI" <<LAUNCH
#!/bin/bash
open -a Terminal "$START_CMD"
LAUNCH
fi
rm -f "$TMP_C"
chmod +x "$APP/Contents/MacOS/GringoAI"

# Icon-Cache auffrischen
touch "$APP"

# Ins Dock legen (nur wenn noch nicht vorhanden)
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Gringo AI.app"; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file:///Applications/Gringo%20AI.app/</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
  killall Dock
fi

echo
echo "✅ Fertig! Gringo AI ist jetzt im Dock und im Programme-Ordner."
echo "   Ein Klick auf das G-Symbol startet Gringo AI."
