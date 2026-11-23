"""Gringo AI – Rap-Briefing (Test).

Eigenständiges Test-Briefing im Rap-Stil, gesprochen mit der Jarvis-Stimme,
dazu läuft auf Spotify (Mac) ein Instrumental. Das normale Briefing bleibt
unverändert – dieses Skript fasst nichts davon an.

Echte Werte:
  * Wetter Heubach + Osijek von Open-Meteo (kostenlos, ohne Anmeldung)
  * offene Notizen aus ~/.openjarvis/gringo-notizen.json (falls vorhanden)
Fehlt ein Wert, fällt die Zeile weg – es wird nichts erfunden.

Einstellungen: ~/.openjarvis/rap-briefing.env
  SPOTIFY_TRACK=spotify:track:…   (wird beim ersten Start abgefragt)
  MUSIK_LAUTSTAERKE=35            (0–100, Spotify-Lautstärke während des Raps)
  TEMPO=1.1                       (Sprechtempo Jarvis, 0.7–1.2)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

CFG_DIR = Path.home() / ".openjarvis"
CFG_FILE = CFG_DIR / "rap-briefing.env"
NOTES_FILE = CFG_DIR / "gringo-notizen.json"

PLACES = {
    "heubach": ("Heubach", 48.7922, 9.9339),
    "hr": ("Osijek", 45.5550, 18.6955),
}
CODES = {
    0: "klarer Himmel", 1: "fast klar", 2: "teils Wolken", 3: "alles grau",
    45: "Nebel", 48: "Nebel mit Reif", 51: "leichter Niesel", 53: "Niesel",
    55: "starker Niesel", 56: "Glatteis-Niesel", 57: "Glatteis-Niesel",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen", 66: "Eisregen",
    67: "Eisregen", 71: "leichter Schnee", 73: "Schnee", 75: "starker Schnee",
    77: "Schneegriesel", 80: "kurze Schauer", 81: "Regenschauer",
    82: "heftige Schauer", 85: "Schneeschauer", 86: "starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Unwetter mit Hagel",
}


# ── Einstellungen ────────────────────────────────────────────────────

def read_cfg() -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        for raw in CFG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def write_cfg(cfg: Dict[str, str]) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Gringo AI – Rap-Briefing (Test)"] + [f"{k}={v}" for k, v in cfg.items()]
    CFG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()


def to_uri(link: str) -> Optional[str]:
    link = link.strip()
    m = re.search(r"track[/:]([A-Za-z0-9]{22})", link)
    return f"spotify:track:{m.group(1)}" if m else None


def ask_track() -> Optional[str]:
    text = osa(
        'try\n'
        'set r to display dialog "Rap-Briefing: Füge den Spotify-Link vom Instrumental ein.'
        '\\n\\nSo geht\'s: In Spotify beim Song auf ••• → Teilen → Link zum Song kopieren." '
        'default answer "" with title "Gringo AI" buttons {"Ohne Musik", "OK"} default button "OK"\n'
        'if button returned of r is "OK" then return text returned of r\n'
        'end try\nreturn ""'
    )
    return to_uri(text) if text else None


# ── Echte Daten ──────────────────────────────────────────────────────

def weather(key: str) -> Optional[Dict[str, str]]:
    name, lat, lon = PLACES[key]
    try:
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "Europe/Berlin", "forecast_days": 1,
            },
            timeout=5.0,
        )
        r.raise_for_status()
        d = r.json()["daily"]
        return {
            "ort": name,
            "min": str(round(d["temperature_2m_min"][0])),
            "max": str(round(d["temperature_2m_max"][0])),
            "text": CODES.get(d["weather_code"][0], ""),
        }
    except Exception:
        return None


def open_notes(n: int = 2) -> List[str]:
    try:
        data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        notes = [x for x in data.get("notes", []) if x.get("status", "offen") == "offen"]
        return [str(x.get("text", "")).strip() for x in notes[:n] if x.get("text")]
    except Exception:
        return []


# ── Text bauen (nur Zeilen mit echten Werten) ────────────────────────

def build_text() -> str:
    out: List[str] = [
        "Yo, Chef, aufwachen – Jarvis am Mic,",
        "Gringo AI, der Morgen ist hart, doch wir sind bereit.",
        "Kaffee auf den Tisch, die Zahlen im Blick,",
        "Briefing im Takt – und keiner schickt uns zurück.",
        "",
    ]
    w = weather("heubach")
    if w:
        out += [
            f"Heubach heute: {w['min']} bis {w['max']} Grad, {w['text']},",
            "Jacke oder Shirt – ich sag's dir, bevor du fragst.",
        ]
    h = weather("hr")
    if h:
        out += [
            f"Unten in Slawonien: {h['min']} bis {h['max']} Grad, {h['text']},",
            "Kroatien ruft, doch erst wird hier Geld gemacht.",
        ]
    if not w and not h:
        out += ["Wetter heute? Keine Daten, Chef – ich rate nicht,",
                "schau kurz raus, das Fenster lügt dich nicht."]
    out.append("")
    notes = open_notes()
    if notes:
        out.append(f"Auf deinem Zettel steht: {notes[0]},")
        if len(notes) > 1:
            out.append(f"und dann noch: {notes[1]},")
        out += [
            "ich vergess' nix, Chef, ich bin dein Kopf aus Stahl,",
            "wenn du's vergisst – na ja, dann merk' ich's mir halt nochmal.",
            "",
        ]
    out += ["Das war's vom Jarvis, Mic geht aus,", "Kopf hoch, Chef – hol heute was raus."]
    return "\n".join(out)


# ── Abspielen ────────────────────────────────────────────────────────

def speak(text: str, tempo: float) -> None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from openjarvis.speech.gringo_jarvis import synthesize_jarvis

        audio = synthesize_jarvis(text, speed=tempo)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            path = f.name
        print("🎤 Jarvis rappt …")
        subprocess.run(["afplay", path])
        Path(path).unlink(missing_ok=True)
    except Exception as e:  # kein Schlüssel / kein Internet → Anna
        print(f"Jarvis nicht verfügbar ({e}) – Anna übernimmt.")
        subprocess.run(["say", "-v", "Anna", "-r", "190", text])


def spotify(script: str) -> str:
    return osa(f'tell application "Spotify" to {script}')


def main() -> None:
    cfg = read_cfg()
    track = cfg.get("SPOTIFY_TRACK", "")
    if not track:
        track = ask_track() or ""
        if track:
            cfg["SPOTIFY_TRACK"] = track
            cfg.setdefault("MUSIK_LAUTSTAERKE", "35")
            cfg.setdefault("TEMPO", "1.1")
            write_cfg(cfg)
    try:
        vol = max(0, min(100, int(cfg.get("MUSIK_LAUTSTAERKE", "35"))))
    except ValueError:
        vol = 35
    try:
        tempo = max(0.7, min(1.2, float(cfg.get("TEMPO", "1.1"))))
    except ValueError:
        tempo = 1.1

    print("Hole Wetter und Notizen …")
    text = build_text()
    print("\n" + text + "\n")

    old_vol = None
    if track:
        old_vol = spotify("get sound volume") or None
        spotify(f"set sound volume to {vol}")
        spotify(f'play track "{track}"')
        time.sleep(4)  # kurzes Intro vom Beat

    speak(text, tempo)

    if track:
        time.sleep(2)
        for v in range(vol, -1, -5):  # Musik ausblenden
            spotify(f"set sound volume to {v}")
            time.sleep(0.15)
        spotify("pause")
        if old_vol and old_vol.isdigit():
            spotify(f"set sound volume to {old_vol}")


if __name__ == "__main__":
    main()
