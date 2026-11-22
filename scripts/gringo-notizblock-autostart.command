#!/usr/bin/env bash
# ── Gringo Notizblock – dauerhaft im Hintergrund ─────────────────────
# Einmal per Doppelklick ausführen: Der Notizblock startet danach bei jeder
# Anmeldung am Mac von selbst (auch wenn Gringo AI nicht läuft).
# Wieder entfernen:  ./scripts/gringo-notizblock-autostart.command entfernen
# ─────────────────────────────────────────────────────────────────────
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LABEL="de.gringo.notizblock"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
pause() { read -r -p "Enter drücken zum Schließen…" _; }

if [ "${1:-}" = "entfernen" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$PLIST"
  echo "Autostart entfernt."; pause; exit 0
fi

PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
[ -n "$PY" ] || { echo "Python nicht gefunden."; pause; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.openjarvis"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string>
    <string>$REPO_ROOT/src/openjarvis/gringo_notes.py</string>
    <string>serve</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.openjarvis/notizblock.log</string>
  <key>StandardErrorPath</key><string>$HOME/.openjarvis/notizblock.log</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" || { echo "Autostart konnte nicht aktiviert werden."; pause; exit 1; }

echo "Fertig! Der Notizblock läuft jetzt im Hintergrund und startet mit dem Mac."
sleep 2
open "http://localhost:8765"
echo "Im Browser findest du unten den „Link fürs Handy“."
pause
