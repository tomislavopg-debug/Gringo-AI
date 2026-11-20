"""macOS ``say`` TTS backend — German voices built into every Mac.

Gringo AI: Kokoro has no German voices, so on macOS we use the system
speech synthesizer (``/usr/bin/say``). It runs fully offline, needs no
extra packages and supports high-quality German voices (e.g. "Anna",
or downloadable premium/Siri voices from System Settings → Accessibility
→ Spoken Content → System Voice → Manage Voices).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

logger = logging.getLogger(__name__)

_SAY = "/usr/bin/say"
# Base speaking rate in words per minute (macOS default is ~175-200).
_BASE_RATE = 185
_SAMPLE_RATE = 22050
# Preferred German voices, best first. Premium/enhanced variants are picked
# automatically when installed because they share the base name.
_PREFERRED_GERMAN = ("Anna", "Petra", "Helena", "Markus", "Yannick", "Martin", "Sandy", "Flo")
_VOICE_LINE = re.compile(r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2}[_-][A-Z]{2})\s+#")


@lru_cache(maxsize=1)
def _list_voices() -> Tuple[Tuple[str, str], ...]:
    """Return ``(name, locale)`` for every installed ``say`` voice."""
    try:
        out = subprocess.run(
            [_SAY, "-v", "?"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except Exception:  # pragma: no cover - only on broken systems
        return ()
    voices = []
    for line in out.splitlines():
        m = _VOICE_LINE.match(line)
        if m:
            voices.append((m.group("name").strip(), m.group("locale").replace("-", "_")))
    return tuple(voices)


def _german_voices() -> List[str]:
    return [name for name, locale in _list_voices() if locale.startswith("de_")]


def _pick_default_voice() -> str:
    german = _german_voices()
    if not german:
        return ""
    for preferred in _PREFERRED_GERMAN:
        # Prefer enhanced/premium variants, e.g. "Anna (Premium)".
        matches = [v for v in german if v.split(" (")[0] == preferred]
        if matches:
            matches.sort(key=lambda v: ("Premium" not in v, "Enhanced" not in v, "Erweitert" not in v))
            return matches[0]
    return german[0]


@TTSRegistry.register("macos_say")
class MacOSSayTTSBackend(TTSBackend):
    """Offline German text-to-speech via the macOS ``say`` command."""

    backend_id = "macos_say"

    def health(self) -> bool:
        return sys.platform == "darwin" and os.path.exists(_SAY) and shutil.which("afconvert") is not None

    def available_voices(self) -> List[str]:
        return [name for name, _ in _list_voices()]

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        voice = voice_id if voice_id and voice_id in self.available_voices() else _pick_default_voice()
        rate = max(80, min(400, int(_BASE_RATE * (speed or 1.0))))

        with tempfile.TemporaryDirectory(prefix="gringo-tts-") as tmp:
            txt = Path(tmp) / "input.txt"
            aiff = Path(tmp) / "speech.aiff"
            wav_path = Path(tmp) / "speech.wav"
            txt.write_text(text, encoding="utf-8")

            cmd = [_SAY, "-r", str(rate), "-o", str(aiff), "-f", str(txt)]
            if voice:
                cmd[1:1] = ["-v", voice]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", f"LEI16@{_SAMPLE_RATE}", str(aiff), str(wav_path)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            audio = wav_path.read_bytes()
            with wave.open(str(wav_path), "rb") as w:
                duration = w.getnframes() / float(w.getframerate() or _SAMPLE_RATE)

        return TTSResult(
            audio=audio,
            format="wav",
            duration_seconds=duration,
            voice_id=voice,
            sample_rate=_SAMPLE_RATE,
        )


__all__ = ["MacOSSayTTSBackend"]
