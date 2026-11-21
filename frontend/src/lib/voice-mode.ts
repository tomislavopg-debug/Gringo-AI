import { create } from 'zustand';

/**
 * Gringo AI: Welche Stimme spricht?
 *  - 'anna'   → kostenlose macOS-Stimme (offline)
 *  - 'jarvis' → eigene Jarvis-Stimme über ElevenLabs (kostet Credits)
 * Die Auswahl wird im Browser gespeichert.
 */
export type VoiceMode = 'anna' | 'jarvis';

const KEY = 'gringo-voice-mode';

function load(): VoiceMode {
  try {
    return localStorage.getItem(KEY) === 'jarvis' ? 'jarvis' : 'anna';
  } catch {
    return 'anna';
  }
}

interface VoiceModeStore {
  mode: VoiceMode;
  /** Grund, falls Jarvis zuletzt nicht sprechen konnte und Anna eingesprungen ist. */
  lastFallback: string | null;
  setMode: (mode: VoiceMode) => void;
  setFallback: (reason: string | null) => void;
}

export const useVoiceMode = create<VoiceModeStore>((set) => ({
  mode: load(),
  lastFallback: null,
  setMode: (mode) => {
    try {
      localStorage.setItem(KEY, mode);
    } catch {
      // Speicher nicht verfügbar – Auswahl gilt dann nur bis zum Neuladen.
    }
    set({ mode, lastFallback: null });
  },
  setFallback: (reason) => set({ lastFallback: reason }),
}));
