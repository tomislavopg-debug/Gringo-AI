#!/usr/bin/env bash
# ── Gringo AI – Schnellstart ─────────────────────────────────────────
# Startet Ollama, Backend und Oberfläche und öffnet den Browser.
# Beim allerersten Mal (oder nach größeren Updates) wird automatisch
# ./scripts/quickstart.sh ausgeführt, das alles installiert.
#
# Beenden: in diesem Fenster  ctrl + C  drücken.
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BOLD='\033[1m'; NC='\033[0m'
info() { echo -e "${BLUE}[info]${NC}  $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}    $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
fail() { echo -e "${RED}[fehler]${NC} $*"; echo; read -r -p "Enter drücken zum Schließen…" _; exit 1; }

# Programme von Homebrew, uv und Rust finden (auch wenn per Doppelklick gestartet)
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || fail "Projektordner nicht gefunden: $REPO_ROOT"

clear
echo -e "${BOLD}"
echo "   ┌──────────────────────────────────┐"
echo "   │           Gringo AI              │"
echo "   └──────────────────────────────────┘"
echo -e "${NC}"

URL="http://localhost:5173"

# ── Automatische Updates von GitHub ──────────────────────────────────
if [ -z "${GRINGO_UPDATED:-}" ] && [ -d .git ]; then
  info "Suche nach Updates…"
  OLD_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
  if git pull --ff-only -q 2>/dev/null; then
    NEW_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
    if [ "$OLD_HEAD" != "$NEW_HEAD" ]; then
      ok "Update installiert."
      # Python-Bausteine nachziehen, falls sich etwas geändert hat
      if ! git diff --quiet "$OLD_HEAD" "$NEW_HEAD" -- pyproject.toml uv.lock 2>/dev/null; then
        info "Aktualisiere Python-Bausteine…"
        uv sync --extra desktop --extra tools-search --quiet || warn "uv sync fehlgeschlagen"
      fi
      if ! git diff --quiet "$OLD_HEAD" "$NEW_HEAD" -- frontend/package.json frontend/package-lock.json 2>/dev/null; then
        info "Aktualisiere Oberfläche…"
        (cd frontend && npm install --silent) || warn "npm install fehlgeschlagen"
      fi
    else
      ok "Alles aktuell."
    fi
  else
    warn "Update nicht möglich (kein Internet?) – starte mit aktueller Version."
  fi
  export GRINGO_UPDATED=1
  exec "$0" "$@"
fi

# Läuft Gringo AI schon? Dann nur den Browser öffnen.
if curl -sf http://localhost:8000/health &>/dev/null && curl -sf "$URL" &>/dev/null; then
  ok "Gringo AI läuft bereits – öffne den Browser."
  open "$URL"
  sleep 2
  exit 0
fi

# Erste Einrichtung noch nicht gemacht? Dann den vollständigen Quickstart nehmen.
if [ ! -d ".venv" ] || [ ! -d "frontend/node_modules" ]; then
  warn "Erste Einrichtung – das dauert beim ersten Mal 10–20 Minuten."
  exec ./scripts/quickstart.sh
fi

PIDS=()
cleanup() {
  echo
  info "Gringo AI wird beendet…"
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do kill "$pid" 2>/dev/null || true; done
  pkill -f "jarvis serve --port 8000" 2>/dev/null || true
  wait 2>/dev/null || true
  ok "Beendet. Du kannst dieses Fenster jetzt schließen."
}
trap cleanup EXIT INT TERM

# 1. Ollama
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
  ok "Ollama läuft"
else
  info "Starte Ollama…"
  command -v ollama &>/dev/null || fail "Ollama nicht gefunden. Bitte 'brew install ollama' ausführen."
  ollama serve &>/dev/null &
  PIDS+=($!)
  for _ in $(seq 1 20); do
    curl -sf http://localhost:11434/api/tags &>/dev/null && break
    sleep 0.5
  done
  curl -sf http://localhost:11434/api/tags &>/dev/null || fail "Ollama startet nicht."
  ok "Ollama gestartet"
fi

# 2. Backend
if curl -sf http://localhost:8000/health &>/dev/null; then
  ok "Backend läuft bereits"
else
  info "Starte Gringo-AI-Backend…"
  # Läuft in einer Schleife: Nach einem Update aus der Gringo-Werkstatt
  # beendet sich das Backend mit Code 42 und wird automatisch neu gestartet.
  (
    export GRINGO_SUPERVISED=1
    while true; do
      uv run jarvis serve --port 8000 >>"$REPO_ROOT/.gringo-backend.log" 2>&1
      code=$?
      [ "$code" -eq 42 ] || break
      echo "[info]  Gringo AI wurde aktualisiert – starte neu…"
      sleep 1
    done
  ) &
  PIDS+=($!)
  for _ in $(seq 1 60); do
    curl -sf http://localhost:8000/health &>/dev/null && break
    sleep 1
  done
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "Backend läuft"
  else
    warn "Backend braucht länger… (Details: .gringo-backend.log)"
  fi
fi

# 3. Oberfläche
info "Starte Oberfläche…"
(cd frontend && npm run dev) &>"$REPO_ROOT/.gringo-frontend.log" &
PIDS+=($!)
for _ in $(seq 1 30); do
  curl -sf "$URL" &>/dev/null && break
  sleep 0.5
done
ok "Oberfläche läuft"

open "$URL"

echo
echo -e "${GREEN}${BOLD}   Gringo AI läuft! 🚀${NC}"
echo
echo "   Im Browser:  $URL"
echo
echo -e "   ${BOLD}Zum Beenden:${NC} in diesem Fenster  ctrl + C  drücken."
echo "   (Dieses Fenster bitte offen lassen.)"
echo

wait
