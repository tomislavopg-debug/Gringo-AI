#!/usr/bin/env bash
# ── Gringo AI – Rap-Briefing (Test) ──────────────────────────────────
# Doppelklick: Jarvis rappt das Briefing, auf Spotify läuft das Instrumental.
# Das normale Briefing bleibt unverändert.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" scripts/gringo_rap_briefing.py
echo
echo "Fertig. Fenster schließt in 5 Sekunden …"
sleep 5
osascript -e 'tell application "Terminal" to close (every window whose name contains "gringo-rap-briefing")' >/dev/null 2>&1 &
exit 0
