'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/shadcn/utils';

/*
 * A− / A / A+ text-size controls, shown on the right of the HUD.
 *
 * They set the `--jarvis-text-scale` CSS variable on <html>, which the
 * conversation transcript consumes via `.jarvis-chat-transcript`. The choice is
 * persisted to localStorage.
 */

const STORAGE_KEY = 'jarvis-text-scale';
const MIN = 0.75;
const MAX = 1.9;
const STEP = 0.15;

const BUTTON_CLASS =
  'pointer-events-auto flex h-7 min-w-7 items-center justify-center border border-cyan-300/40 ' +
  'bg-slate-950/50 px-1.5 text-[10px] font-bold tracking-[0.1em] text-cyan-100 backdrop-blur-sm ' +
  'transition-colors hover:border-cyan-200/70 hover:bg-cyan-400/15 ' +
  'focus-visible:border-cyan-200 focus-visible:outline-none';

export function TextSizeControls() {
  const [scale, setScale] = useState(1);

  // Restore persisted preference after mount.
  useEffect(() => {
    const saved = Number(window.localStorage.getItem(STORAGE_KEY));
    if (Number.isFinite(saved) && saved >= MIN && saved <= MAX) {
      setScale(saved);
    }
  }, []);

  // Apply + persist.
  useEffect(() => {
    document.documentElement.style.setProperty('--jarvis-text-scale', String(scale));
    window.localStorage.setItem(STORAGE_KEY, String(scale));
  }, [scale]);

  const clamp = (value: number) => Math.min(MAX, Math.max(MIN, Math.round(value * 100) / 100));

  return (
    <div className="absolute top-[15.5%] right-[3.2%] z-10 flex items-center gap-1">
      <span className="mr-1 text-[8px] tracking-[0.3em] text-cyan-300/60">TEXT</span>
      <button
        type="button"
        aria-label="Decrease conversation text size"
        title="Decrease text size"
        className={cn(BUTTON_CLASS)}
        onClick={() => setScale((s) => clamp(s - STEP))}
      >
        A−
      </button>
      <button
        type="button"
        aria-label="Reset conversation text size"
        title="Reset text size"
        className={cn(BUTTON_CLASS)}
        onClick={() => setScale(1)}
      >
        A
      </button>
      <button
        type="button"
        aria-label="Increase conversation text size"
        title="Increase text size"
        className={cn(BUTTON_CLASS)}
        onClick={() => setScale((s) => clamp(s + STEP))}
      >
        A+
      </button>
    </div>
  );
}
