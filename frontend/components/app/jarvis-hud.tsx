'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/shadcn/utils';

/*
 * Full-screen Iron Man / Jarvis HUD.
 *
 * Rendered behind the agent session view (z-0) while a call is connected. It is
 * purely decorative (pointer-events-none) and always dark, independent of the
 * app theme. The central figure is a local wireframe asset
 * (/public/iron-man-wireframe.png) derived from the project artwork.
 */

const CYAN = 'rgba(34, 211, 238, 0.75)';
const CYAN_DIM = 'rgba(34, 211, 238, 0.38)';
const CYAN_FAINT = 'rgba(34, 211, 238, 0.18)';

// Aspect ratio (width / height) of /public/iron-man-wireframe.png.
const FIGURE_ASPECT = 1.079;

// The arc reactor sits on the chest of the wireframe, as a fraction of the
// figure box (measured from the source artwork).
const REACTOR_LEFT = '47.5%';
const REACTOR_TOP = '80.5%';

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

function pad(value: number) {
  return value.toString().padStart(2, '0');
}

/** Clock that only ticks on the client, avoiding hydration mismatches. */
function useClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return now;
}

/* -------------------------------------------------------------------------- */
/* Top measurement scale                                                       */
/* -------------------------------------------------------------------------- */

function TopScale() {
  const ticks = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

  return (
    <div className="absolute inset-x-0 top-[1.4%] h-9">
      <div className="relative mx-auto h-full w-[94%]">
        {/* baseline */}
        <div className="absolute inset-x-0 top-3 h-px bg-cyan-300/45" />

        {/* minor ticks */}
        <div
          className="absolute inset-x-0 top-3 h-1.5"
          style={{
            backgroundImage:
              'repeating-linear-gradient(to right, rgba(103,232,249,0.55) 0 1px, transparent 1px 0.8%)',
          }}
        />

        {/* major ticks + labels */}
        {ticks.map((tick) => (
          <div key={tick} className="absolute top-3 -translate-x-1/2" style={{ left: `${tick}%` }}>
            <div className="mx-auto h-3 w-px bg-cyan-200/80" />
            <div className="mt-0.5 text-center text-[8px] leading-none tracking-[0.2em] text-cyan-300/70">
              {tick}
            </div>
          </div>
        ))}

        {/* end caps */}
        <div className="absolute top-1 left-0 h-5 w-px bg-cyan-200/80" />
        <div className="absolute top-1 right-0 h-5 w-px bg-cyan-200/80" />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Digital clock (upper right)                                                 */
/* -------------------------------------------------------------------------- */

function Clock() {
  const now = useClock();

  const time = now
    ? `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
    : '--:--:--';
  const date = now
    ? `${WEEKDAYS[now.getDay()]} · ${pad(now.getDate())} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`
    : '';

  return (
    <div className="absolute top-[6%] right-[3.2%] z-10 text-right">
      <div className="flex items-baseline justify-end gap-2">
        <span className="text-[9px] tracking-[0.35em] text-cyan-300/60">LOCAL</span>
        <span className="text-[clamp(1.5rem,2.6vw,2.4rem)] leading-none font-light tracking-[0.12em] text-cyan-100 tabular-nums [text-shadow:0_0_16px_rgba(34,211,238,0.55)]">
          {time}
        </span>
      </div>
      <div className="mt-1 text-[9px] tracking-[0.34em] text-cyan-300/70">{date}</div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Compact indicators (below the top scale)                                    */
/* -------------------------------------------------------------------------- */

function Chip({
  label,
  value,
  tone = 'cyan',
}: {
  label: string;
  value: string;
  tone?: 'cyan' | 'amber';
}) {
  return (
    <div className="flex items-center gap-1.5 border border-cyan-400/25 bg-cyan-400/5 px-2 py-1">
      <span className="text-[8px] tracking-[0.2em] text-cyan-300/60">{label}</span>
      <span
        className={cn(
          'text-[9px] font-bold tracking-[0.16em]',
          tone === 'amber' ? 'text-amber-300' : 'text-cyan-100'
        )}
      >
        {value}
      </span>
    </div>
  );
}

function Indicators() {
  return (
    <>
      <div className="absolute top-[5.8%] left-[3.2%] z-10 flex flex-wrap gap-1.5">
        <Chip label="PWR" value="98%" />
        <Chip label="CORE" value="STABLE" />
        <Chip label="LINK" value="12MS" />
      </div>
      <div className="absolute top-[5.8%] right-[3.2%] z-10 flex flex-wrap justify-end gap-1.5 pr-[24vw]">
        <Chip label="SYS" value="ONLINE" />
        <Chip label="MEM" value="42%" />
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Side readouts + fine HUD lines                                              */
/* -------------------------------------------------------------------------- */

interface Readout {
  label: string;
  value: string;
  meter: number;
  tone?: 'cyan' | 'amber';
}

const LEFT_READOUTS: Readout[] = [
  { label: 'POWER CORE', value: '98%', meter: 0.98 },
  { label: 'REPULSOR 01', value: '100%', meter: 1 },
  { label: 'REPULSOR 02', value: '100%', meter: 1 },
  { label: 'FLIGHT SYS', value: 'STANDBY', meter: 0.34, tone: 'amber' },
  { label: 'TARGETING', value: 'CALIBRATING', meter: 0.62 },
];

const RIGHT_READOUTS: Readout[] = [
  { label: 'UPLINK', value: 'LIVEKIT', meter: 1 },
  { label: 'AI CORE', value: 'GEMINI LIVE', meter: 0.92 },
  { label: 'ENCRYPTION', value: 'AES-256', meter: 1 },
  { label: 'MEMORY', value: 'SQLITE', meter: 0.74 },
  { label: 'THREAT', value: 'LOW', meter: 0.18 },
];

function ReadoutRow({ item, align }: { item: Readout; align: 'left' | 'right' }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className={cn(
          'flex w-full items-baseline gap-2 text-[9px] tracking-[0.16em]',
          align === 'right' && 'flex-row-reverse text-right'
        )}
      >
        <span className="whitespace-nowrap text-cyan-300/60">{item.label}</span>
        <span className="min-w-3 flex-1 border-b border-dotted border-cyan-400/25" />
        <span
          className={cn(
            'whitespace-nowrap',
            item.tone === 'amber' ? 'text-amber-300' : 'text-cyan-100'
          )}
        >
          {item.value}
        </span>
      </div>
      <div className={cn('h-[3px] w-[78%] bg-cyan-400/10', align === 'right' && 'self-end')}>
        <div
          className="h-full bg-cyan-300/80 shadow-[0_0_6px_rgba(34,211,238,0.8)]"
          style={{ width: `${Math.round(item.meter * 100)}%` }}
        />
      </div>
    </div>
  );
}

function SideReadouts() {
  return (
    <>
      <div className="absolute top-[27%] left-[3.2%] z-10 flex w-[13%] min-w-[130px] flex-col gap-3.5">
        {LEFT_READOUTS.map((item) => (
          <ReadoutRow key={item.label} item={item} align="left" />
        ))}
      </div>

      <div className="absolute top-[27%] right-[3.2%] z-10 flex w-[13%] min-w-[130px] flex-col gap-3.5">
        {RIGHT_READOUTS.map((item) => (
          <ReadoutRow key={item.label} item={item} align="right" />
        ))}
      </div>

      {/* fine HUD connector lines */}
      <svg
        className="absolute inset-0 z-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <g fill="none" stroke={CYAN_DIM} strokeWidth="0.08">
          <path d="M16 30 L22 30 L24 32 L28 32" />
          <path d="M16 46 L21 46 L24 43 L28 43" />
          <path d="M84 30 L78 30 L76 32 L72 32" />
          <path d="M84 46 L79 46 L76 43 L72 43" />
          <path d="M16 62 L22 62 L24 60 L26 60" />
          <path d="M84 62 L78 62 L76 60 L74 60" />
        </g>
        <g fill={CYAN}>
          <circle cx="28" cy="32" r="0.35" />
          <circle cx="28" cy="43" r="0.35" />
          <circle cx="72" cy="32" r="0.35" />
          <circle cx="72" cy="43" r="0.35" />
        </g>
      </svg>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Lower-left hexagonal pattern                                                */
/* -------------------------------------------------------------------------- */

function HexPattern() {
  return (
    <div className="absolute bottom-[15vh] left-[3.4%] z-10 h-[15vh] w-[21vh] opacity-80">
      <div className="mb-1 text-[8px] tracking-[0.3em] text-cyan-300/60">NANO-LATTICE</div>
      <svg viewBox="0 0 220 150" className="h-[calc(100%-12px)] w-full" aria-hidden="true">
        <defs>
          <pattern id="jarvis-hex" width="30" height="26" patternUnits="userSpaceOnUse">
            <path
              d="M15 0 L30 7.5 L30 18.5 L15 26 L0 18.5 L0 7.5 Z"
              fill="none"
              stroke="rgba(34,211,238,0.4)"
              strokeWidth="1"
            />
            <path
              d="M0 26 L0 33 M30 26 L30 33 M15 26 L15 33"
              stroke="rgba(34,211,238,0.16)"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="220" height="150" fill="url(#jarvis-hex)" />
        <rect
          x="0.5"
          y="0.5"
          width="219"
          height="149"
          fill="none"
          stroke="rgba(34,211,238,0.35)"
          strokeWidth="1"
        />
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Lower-right wireframe globe                                                 */
/* -------------------------------------------------------------------------- */

function HudGlobe() {
  const size = 104;
  const cx = 100;
  const cy = 100;
  const r = 88;

  const parallels = [-60, -30, 0, 30, 60].map((lat) => {
    const rad = (lat * Math.PI) / 180;
    return { y: cy - r * Math.sin(rad), rx: r * Math.cos(rad) };
  });

  const meridians = [30, 60, 90].map((deg) => r * Math.sin((deg * Math.PI) / 180));

  return (
    <div className="absolute right-[3.4%] bottom-[15vh] z-10 h-[16vh] w-[16vh]">
      <div className="mb-1 text-right text-[8px] tracking-[0.3em] text-cyan-300/60">
        ORBITAL MAP
      </div>
      <svg viewBox="0 0 200 200" className="h-[calc(100%-12px)] w-full" aria-hidden="true">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={CYAN} strokeWidth="1.2" />
        <circle cx={cx} cy={cy} r={r + 6} fill="none" stroke={CYAN_FAINT} strokeWidth="1" />

        {parallels.map((p, i) => (
          <ellipse
            key={`p${i}`}
            cx={cx}
            cy={p.y}
            rx={Math.max(p.rx, 0.5)}
            ry={size * 0.06}
            fill="none"
            stroke={CYAN_DIM}
            strokeWidth="1"
          />
        ))}
        {meridians.map((rx, i) => (
          <ellipse
            key={`m${i}`}
            cx={cx}
            cy={cy}
            rx={rx}
            ry={r}
            fill="none"
            stroke={CYAN_DIM}
            strokeWidth="1"
          />
        ))}
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke={CYAN_DIM} strokeWidth="1" />

        {/* radar sweep */}
        <g>
          <line x1={cx} y1={cy} x2={cx} y2={cy - r} stroke={CYAN} strokeWidth="1.2" />
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${cx} ${cy}`}
            to={`360 ${cx} ${cy}`}
            dur="9s"
            repeatCount="indefinite"
          />
        </g>
        <circle cx={cx} cy={cy} r="2.5" fill={CYAN} />
        <circle cx="142" cy="66" r="2" fill="rgba(125,240,255,0.9)" />
        <circle cx="72" cy="120" r="2" fill="rgba(125,240,255,0.9)" />
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Central chest arc reactor                                                   */
/* -------------------------------------------------------------------------- */

function ArcReactor({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div className={cn('absolute -translate-x-1/2 -translate-y-1/2', className)} style={style}>
      <div className="absolute top-1/2 left-1/2 -z-10 aspect-square w-[330%] -translate-x-1/2 -translate-y-1/2">
        <div className="jarvis-reactor-glow h-full w-full rounded-full" />
      </div>
      <svg viewBox="0 0 100 100" className="relative h-full w-full" aria-hidden="true">
        <defs>
          <radialGradient id="jarvis-reactor-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#eafcff" />
            <stop offset="35%" stopColor="#9ceaff" />
            <stop offset="70%" stopColor="#38c7ff" />
            <stop offset="100%" stopColor="#0a7bff" />
          </radialGradient>
        </defs>
        <circle
          cx="50"
          cy="50"
          r="46"
          fill="none"
          stroke={CYAN_DIM}
          strokeWidth="1.5"
          strokeDasharray="5 5"
        />
        <circle cx="50" cy="50" r="36" fill="none" stroke={CYAN} strokeWidth="1.5" />
        {/* triangular core plate */}
        <path
          d="M50 22 L72 62 L28 62 Z"
          fill="none"
          stroke="rgba(150,240,255,0.85)"
          strokeWidth="1.5"
        />
        <circle cx="50" cy="50" r="20" fill="url(#jarvis-reactor-core)" />
        <circle cx="50" cy="50" r="20" fill="none" stroke="#dffaff" strokeWidth="1" opacity="0.8" />
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Bottom curved, segmented HUD arc                                            */
/* -------------------------------------------------------------------------- */

function CentralEmblem() {
  return (
    <svg viewBox="0 0 100 100" className="h-full w-full" aria-hidden="true">
      <circle
        cx="50"
        cy="50"
        r="46"
        fill="none"
        stroke={CYAN_DIM}
        strokeWidth="2"
        strokeDasharray="6 6"
      />
      <circle cx="50" cy="50" r="34" fill="none" stroke={CYAN} strokeWidth="2" />
      <path d="M50 24 L70 62 L30 62 Z" fill="none" stroke="rgba(160,240,255,0.9)" strokeWidth="3" />
      <circle cx="50" cy="50" r="9" fill="#bff4ff" />
    </svg>
  );
}

function BottomArc() {
  const now = useClock();
  const date = now ? `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}` : '';

  return (
    <div className="absolute inset-x-0 bottom-0 z-10 h-[26vh]">
      <svg
        viewBox="0 0 1440 260"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <path
          d="M -80 40 Q 720 340 1520 40"
          fill="none"
          stroke={CYAN}
          strokeWidth="1.4"
          strokeDasharray="26 12"
        />
        <path
          d="M -80 14 Q 720 312 1520 14"
          fill="none"
          stroke={CYAN_DIM}
          strokeWidth="1"
          strokeDasharray="4 9"
        />
        <path d="M 40 66 Q 720 316 1400 66" fill="none" stroke={CYAN_FAINT} strokeWidth="1" />
      </svg>

      {/* SIGNAL (left) */}
      <div className="absolute bottom-[6.5vh] left-[7%] text-left">
        <div className="text-[8px] tracking-[0.35em] text-cyan-300/60">SIGNAL</div>
        <div className="mt-1 flex items-end gap-0.5" aria-hidden="true">
          {[5, 9, 14, 20, 16, 11, 7].map((h, i) => (
            <span
              key={i}
              className="w-1 bg-cyan-300/80 shadow-[0_0_6px_rgba(34,211,238,0.7)]"
              style={{ height: `${h}px` }}
            />
          ))}
        </div>
      </div>

      {/* BATTERY (right) */}
      <div className="absolute right-[7%] bottom-[6.5vh] text-right">
        <div className="text-[8px] tracking-[0.35em] text-cyan-300/60">BATTERY</div>
        <div className="mt-1 flex items-center justify-end gap-1">
          <div className="flex h-3 w-24 items-center rounded-[2px] border border-cyan-300/50 p-[2px]">
            <div className="h-full w-[86%] bg-cyan-300/80 shadow-[0_0_6px_rgba(34,211,238,0.7)]" />
          </div>
          <span className="text-[9px] tracking-[0.1em] text-cyan-100">86%</span>
        </div>
      </div>

      {/* central date + emblem */}
      <div className="absolute bottom-[0.6vh] left-1/2 -translate-x-1/2 text-center">
        <div className="text-[8px] tracking-[0.5em] text-cyan-300/70">{date}</div>
      </div>
      <div className="absolute bottom-[3.1vh] left-1/2 h-[2.6vh] w-[2.6vh] -translate-x-1/2">
        <CentralEmblem />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Corner brackets                                                             */
/* -------------------------------------------------------------------------- */

function CornerBrackets() {
  const corners = [
    'top-3 left-3 border-t border-l',
    'top-3 right-3 border-t border-r',
    'bottom-3 left-3 border-b border-l',
    'bottom-3 right-3 border-b border-r',
  ];
  return (
    <>
      {corners.map((c) => (
        <div key={c} className={cn('absolute z-10 h-5 w-5 border-cyan-300/40', c)} />
      ))}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Root                                                                        */
/* -------------------------------------------------------------------------- */

export function JarvisHud() {
  return (
    <div
      aria-hidden="true"
      className="jarvis-hud pointer-events-none fixed inset-0 z-0 overflow-hidden font-mono text-cyan-100 select-none"
    >
      {/* background layers */}
      <div className="jarvis-hud-grid absolute inset-0" />
      <div className="jarvis-hud-scan absolute inset-0" />
      <div className="jarvis-hud-vignette absolute inset-0" />

      {/* central wireframe figure + arc reactor */}
      <div
        className="absolute top-[47%] left-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ height: 'min(76vh, 56vw)' }}
      >
        <div className="relative h-full" style={{ aspectRatio: `${FIGURE_ASPECT}` }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/iron-man-wireframe.png"
            alt=""
            className="jarvis-figure h-full w-full object-contain"
          />
          <ArcReactor
            className="aspect-square w-[14%]"
            style={{ left: REACTOR_LEFT, top: REACTOR_TOP }}
          />
        </div>
      </div>

      {/* HUD chrome */}
      <TopScale />
      <Indicators />
      <Clock />
      <SideReadouts />
      <HexPattern />
      <HudGlobe />
      <BottomArc />
      <CornerBrackets />
    </div>
  );
}
