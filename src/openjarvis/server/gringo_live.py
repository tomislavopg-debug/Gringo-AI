"""Gringo AI: echte Live-Daten statt Raten.

Wenn der Chef nach dem Wetter fragt, holen wir echte Werte von Open-Meteo
(kostenlos, ohne Anmeldung) und geben sie dem Modell mit. So muss das Modell
nichts erfinden. Klappt der Abruf nicht, sagen wir dem Modell ausdrücklich,
dass es keine Wetterdaten gibt.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_WEATHER_WORDS = re.compile(
    r"wetter|regen|regnet|sonne|sonnig|schnee|schneit|temperatur|grad\b|kalt|warm|"
    r"hitze|frost|gewitter|wind|bewölkt|bewoelkt|vorhersage|weather|vrijeme|prognoza",
    re.IGNORECASE,
)

# (Anzeigename, Breite, Länge)
_PLACES: List[Tuple[str, float, float]] = [
    ("Heubach (Ostalbkreis)", 48.7922, 9.9339),
    ("Osijek (Slawonien, Kroatien)", 45.5550, 18.6955),
]
_CROATIA_EXTRA: Dict[str, Tuple[str, float, float]] = {
    "zagreb": ("Zagreb", 45.8150, 15.9819),
    "split": ("Split", 43.5081, 16.4402),
    "rijeka": ("Rijeka", 45.3271, 14.4422),
    "zadar": ("Zadar", 44.1194, 15.2314),
    "dubrovnik": ("Dubrovnik", 42.6507, 18.0944),
    "vukovar": ("Vukovar", 45.3519, 19.0022),
    "đakovo": ("Đakovo", 45.3084, 18.4108),
    "djakovo": ("Đakovo", 45.3084, 18.4108),
    "pula": ("Pula", 44.8666, 13.8496),
    "skopje": ("Skopje (Nordmazedonien)", 41.9981, 21.4254),
}

_CODES = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt",
    45: "Nebel", 48: "Nebel mit Reif", 51: "leichter Nieselregen", 53: "Nieselregen",
    55: "starker Nieselregen", 56: "gefrierender Niesel", 57: "gefrierender Niesel",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen", 66: "gefrierender Regen",
    67: "gefrierender Regen", 71: "leichter Schneefall", 73: "Schneefall",
    75: "starker Schneefall", 77: "Schneegriesel", 80: "leichte Regenschauer",
    81: "Regenschauer", 82: "heftige Regenschauer", 85: "Schneeschauer",
    86: "starke Schneeschauer", 95: "Gewitter", 96: "Gewitter mit Hagel",
    99: "starkes Gewitter mit Hagel",
}

_CACHE: Dict[Tuple[float, float], Tuple[float, str]] = {}
_TTL_S = 15 * 60


def _fetch(name: str, lat: float, lon: float) -> Optional[str]:
    key = (lat, lon)
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _TTL_S:
        return cached[1]
    resp = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Europe/Berlin",
            "forecast_days": 3,
        },
        timeout=4.0,
    )
    resp.raise_for_status()
    data = resp.json()
    cur = data.get("current", {})
    daily = data.get("daily", {})
    lines = [
        f"{name} – jetzt: {cur.get('temperature_2m')} °C (gefühlt {cur.get('apparent_temperature')} °C), "
        f"{_CODES.get(cur.get('weather_code'), 'unbekannt')}, Wind {cur.get('wind_speed_10m')} km/h"
    ]
    labels = ["heute", "morgen", "übermorgen"]
    for i, day in enumerate(daily.get("time", [])[:3]):
        lines.append(
            f"  {labels[i]} ({day}): {daily['temperature_2m_min'][i]} bis "
            f"{daily['temperature_2m_max'][i]} °C, {_CODES.get(daily['weather_code'][i], 'unbekannt')}, "
            f"Regenwahrscheinlichkeit {daily['precipitation_probability_max'][i]} %"
        )
    text = "\n".join(lines)
    _CACHE[key] = (time.time(), text)
    return text


def weather_context(user_text: str) -> Optional[str]:
    """Systemprompt-Zusatz mit echten Wetterdaten, oder None wenn nicht gefragt."""
    if not user_text or not _WEATHER_WORDS.search(user_text):
        return None
    places = list(_PLACES)
    lower = user_text.lower()
    for word, place in _CROATIA_EXTRA.items():
        if word in lower and place not in places:
            places.append(place)

    parts: List[str] = []
    for name, lat, lon in places:
        try:
            text = _fetch(name, lat, lon)
            if text:
                parts.append(text)
        except Exception:
            logger.warning("Wetterabruf für %s fehlgeschlagen", name, exc_info=True)

    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    if not parts:
        return (
            "## Wetterdaten\n"
            "Die Wetterdaten konnten gerade NICHT abgerufen werden (kein Internet?). "
            "Sag dem Chef ehrlich, dass du das Wetter gerade nicht nachschauen kannst. "
            "Nenne auf keinen Fall Temperaturen oder Vorhersagen."
        )
    return (
        f"## Echte Wetterdaten (Open-Meteo, abgerufen {stamp})\n"
        + "\n".join(parts)
        + "\n\nBenutze für Wetterfragen AUSSCHLIESSLICH diese Werte. Erfinde nichts dazu. "
        "Für Orte, die hier nicht stehen, sag ehrlich, dass du dafür keine Daten hast."
    )
