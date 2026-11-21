import { useEffect, useState } from 'react';
import { fetchJarvisVoiceStatus } from '../../lib/api';
import { useVoiceMode } from '../../lib/voice-mode';

/**
 * Gringo AI: Gut sichtbarer Schalter zwischen Anna (kostenlos) und der
 * eigenen Jarvis-Stimme (ElevenLabs, kostet Credits).
 */
export function VoiceModeToggle() {
  const mode = useVoiceMode((s) => s.mode);
  const setMode = useVoiceMode((s) => s.setMode);
  const lastFallback = useVoiceMode((s) => s.lastFallback);
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const check = () => fetchJarvisVoiceStatus().then((s) => alive && setReady(s.ready));
    check();
    const id = setInterval(check, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const jarvis = mode === 'jarvis';

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setMode(jarvis ? 'anna' : 'jarvis')}
        aria-pressed={jarvis}
        className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold transition-colors cursor-pointer"
        style={
          jarvis
            ? {
                background: '#f59e0b',
                border: '2px solid #fbbf24',
                color: '#1a1200',
                boxShadow: '0 0 12px rgba(245, 158, 11, 0.7)',
              }
            : {
                background: 'transparent',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
              }
        }
        title={
          jarvis
            ? 'Jarvis-Stimme ist AN (ElevenLabs, verbraucht Credits). Klicken für Anna.'
            : 'Anna spricht (kostenlos). Klicken für die Jarvis-Stimme (ElevenLabs, kostet Credits).'
        }
      >
        {jarvis ? (
          <>
            <span
              className="inline-block w-2 h-2 rounded-full animate-pulse"
              style={{ background: '#dc2626' }}
            />
            🎩 JARVIS-STIMME AN
          </>
        ) : (
          <>🔊 Stimme: Anna</>
        )}
      </button>
      {jarvis && ready === false && (
        <div className="text-[11px]" style={{ color: 'var(--color-error)' }}>
          ⚠️ Kein ElevenLabs-Schlüssel eingetragen – Anna spricht.
        </div>
      )}
      {jarvis && ready !== false && lastFallback && (
        <div className="text-[11px]" style={{ color: 'var(--color-error)' }}>
          ⚠️ Jarvis gerade nicht erreichbar – Anna ist eingesprungen ({lastFallback}).
        </div>
      )}
    </div>
  );
}
