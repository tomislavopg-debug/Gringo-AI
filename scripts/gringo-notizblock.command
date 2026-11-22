#!/usr/bin/env bash
# ── Gringo Notizblock – Starten ──────────────────────────────────────
# Doppelklick: startet den Notizblock und öffnet ihn im Browser.
# Läuft unabhängig von Gringo AI. Beenden: ctrl + C oder Fenster schließen.
# Dauerhaft im Hintergrund (startet mit dem Mac):
#   scripts/gringo-notizblock-autostart.command
# ─────────────────────────────────────────────────────────────────────
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
[ -n "$PY" ] || { echo "Python nicht gefunden."; read -r -p "Enter drücken zum Schließen…" _; exit 1; }

# Läuft der Notizblock schon (z. B. per Autostart)? Dann nur öffnen.
if curl -sf http://localhost:8765/api/notes &>/dev/null; then
  echo "Der Notizblock läuft schon – öffne ihn im Browser."
  open "http://localhost:8765"
  sleep 2
  exit 0
fi

exec "$PY" "$REPO_ROOT/src/openjarvis/gringo_notes.py" serve --open
