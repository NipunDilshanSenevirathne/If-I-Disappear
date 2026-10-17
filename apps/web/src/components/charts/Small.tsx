/** A tiny line of the last few values (decorative: the number next to it carries the meaning). */
export function Sparkline({ values, color = "var(--brand)", width = 92, height = 30 }: { values: number[]; color?: string; width?: number; height?: number }) {
  if (values.length < 2) values = [values[0] ?? 0, values[0] ?? 0];
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * (width - 4) + 2, max === min ? height / 2 : height - 3 - ((v - min) / span) * (height - 6)] as const);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="sparkline">
      {max !== min && <path d={`${d} L${width - 2},${height} L2,${height} Z`} fill={color} opacity={0.1} />}
      <path d={d} fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r={3.2} fill={color} />
    </svg>
  );
}

/** A progress ring with the value written inside. */
export function Ring({ value, max, size = 64, stroke = 7, color = "var(--brand)", label }: { value: number; max: number; size?: number; stroke?: number; color?: string; label: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} className="ring">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${frac * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="ring-arc"
      />
    </svg>
  );
}
