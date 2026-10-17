import { useId } from "react";

/** The lamp: a flame kept burning in a cupped hand. The household keeps things going. */
export function LampMark({ size = 36 }: { size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="lamp-mark">
      <defs>
        <linearGradient id={`bg${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#14808f" />
          <stop offset="1" stopColor="#0a4a55" />
        </linearGradient>
        <linearGradient id={`fl${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd27a" />
          <stop offset="1" stopColor="#f3a712" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#bg${id})`} />
      <path className="lamp-flame" d="M32 12c6.5 8.6 10 13.7 10 19.4A10 10 0 0 1 22 31.4C22 25.7 25.5 20.6 32 12z" fill={`url(#fl${id})`} />
      <path d="M32 24.5c2.6 3.6 4 5.9 4 8.2a4 4 0 0 1-8 0c0-2.3 1.4-4.6 4-8.2z" fill="#fff6e3" />
      <path d="M17 44c4 4.7 9 7 15 7s11-2.3 15-7" fill="none" stroke="#fff6e3" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <LampMark size={compact ? 30 : 36} />
      <span className="brand-name">If I Disappear</span>
    </span>
  );
}
