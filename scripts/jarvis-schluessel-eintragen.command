#!/usr/bin/env bash
# Öffnet die Datei für den ElevenLabs-Schlüssel (Jarvis-Stimme) in TextEdit.
FILE="$HOME/.openjarvis/elevenlabs.env"
mkdir -p "$HOME/.openjarvis"
if [ ! -f "$FILE" ]; then
  printf '# Gringo AI – ElevenLabs-Schlüssel für die Jarvis-Stimme\n# Ersetze HIER_DEN_SCHLUESSEL_EINFUEGEN durch deinen Schlüssel (beginnt mit sk_) und speichere (⌘ S).\nELEVENLABS_API_KEY=HIER_DEN_SCHLUESSEL_EINFUEGEN\n' > "$FILE"
fi
chmod 600 "$FILE"
open -e "$FILE"
osascript -e 'tell application "Terminal" to close (every window whose name contains "jarvis-schluessel")' >/dev/null 2>&1 &
exit 0
