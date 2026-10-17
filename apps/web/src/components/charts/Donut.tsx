import type { ReactNode } from "react";

export interface Slice {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** A ring split by readiness state. Segments ease to new values when the data changes.
 *  A visually hidden table carries the same numbers for screen readers. */
export function Donut({ slices, size = 188, thickness = 20, center, label }: { slices: Slice[]; size?: number; thickness?: number; center?: ReactNode; label: string }) {
  const total = slices.reduce((n, s) => n + s.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const gap = total > 1 ? 4 : 0;
  let offset = 0;
  return (
    <div className="donut" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={thickness} />
        {total > 0 &&
          slices.map((s) => {
            if (!s.value) return null;
            const len = (s.value / total) * c;
            const dash = Math.max(0.001, len - gap);
            const el = (
              <circle
                key={s.key}
                className="donut-seg"
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={thickness}
                strokeLinecap="butt"
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
              />
            );
            offset += len;
            return el;
          })}
      </svg>
      {center && <div className="donut-center">{center}</div>}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>
          {slices.map((s) => (
            <tr key={s.key}>
              <th scope="row">{s.label}</th>
              <td>{s.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ slices, total }: { slices: Slice[]; total: number }) {
  return (
    <ul className="legend">
      {slices.map((s) => (
        <li key={s.key}>
          <span className="legend-swatch" style={{ background: s.color }} aria-hidden="true" />
          <span className="legend-label">{s.label}</span>
          <span className="legend-value num">{s.value}</span>
          <span className="legend-pct num faint">{total ? Math.round((100 * s.value) / total) : 0}%</span>
        </li>
      ))}
    </ul>
  );
}
