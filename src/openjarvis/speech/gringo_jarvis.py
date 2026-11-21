"""Gringo AI: eigene Jarvis-Stimme über ElevenLabs.

Der API-Schlüssel steht in ``~/.openjarvis/elevenlabs.env`` (vom Nutzer selbst
eingetragen) oder in der Umgebungsvariable ``ELEVENLABS_API_KEY``.
Die Datei wird bei jedem Aufruf neu gelesen – kein Neustart nötig.
"""

from __future__ import annotations

import os
from typing import Dict

from openjarvis.core.paths import get_config_dir

JARVIS_VOICE_ID_DEFAULT = "s3SX4Oeou1unISRW4b88"


def _env_file_values() -> Dict[str, str]:
    path = get_config_dir() / "elevenlabs.env"
    values: Dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _settings() -> Dict[str, str]:
    file_values = _env_file_values()
    key = file_values.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")
    if key.startswith("HIER"):
        key = ""
    voice = (
        file_values.get("GRINGO_JARVIS_VOICE_ID")
        or os.environ.get("GRINGO_JARVIS_VOICE_ID")
        or JARVIS_VOICE_ID_DEFAULT
    )
    return {"key": key, "voice": voice}


def jarvis_status() -> Dict[str, object]:
    s = _settings()
    return {"ready": bool(s["key"]), "voice_id": s["voice"]}


def synthesize_jarvis(text: str, speed: float = 1.0) -> bytes:
    """Spricht *text* mit der Jarvis-Stimme und gibt WAV-Bytes zurück."""
    from openjarvis.speech.elevenlabs_tts import ElevenLabsTTSBackend

    s = _settings()
    if not s["key"]:
        raise RuntimeError("Kein ElevenLabs-Schlüssel eingetragen")
    backend = ElevenLabsTTSBackend(
        api_key=s["key"], model="eleven_multilingual_v2", voice_id=s["voice"]
    )
    result = backend.synthesize(text, voice_id=s["voice"], speed=speed, output_format="wav")
    return result.audio
