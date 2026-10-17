import { useId, useState } from "react";
import { useWidth } from "./useSize";

export interface TrendPoint {
  key: string;
  label: string; // what changed
  when: string; // short time label
  ready: number;
  total: number;
}

/** Readiness after each change (solid), and where the current plan would take it (dashed). */
export function TrendChart({ points, projected, height = 260 }: { points: TrendPoint[]; projected: { ready: number; label: string } | null; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const gid = useId().replace(/:/g, "");
  const [focus, setFocus] = useState<number | null>(null);
  const pad = { top: 66, right: 18, bottom: 34, left: 28 }; // room above the line for the tooltip
  const total = Math.max(1, ...points.map((p) => p.total));
  const all = projected ? [...points, { key: "plan", label: projected.label, when: "With the plan", ready: projected.ready, total }] : points;
  const n = Math.max(2, all.length);
  const plotW = Math.max(10, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;
  const x = (i: number) => pad.left + (all.length === 1 ? plotW / 2 : (plotW * i) / (n - 1));
  const y = (v: number) => pad.top + plotH - (v / total) * plotH;
  const solid = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.ready)}`).join(" ");
  const area = points.length ? `${solid} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z` : "";
  const last = points.length - 1;
  const shown = focus ?? last;
  const sp = all[shown];

  return (
    <div className="trend" ref={ref} style={{ height }}>
      <svg width={width} height={height} aria-hidden="true">
        <defs>
          <linearGradient id={`g${gid}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="var(--brand)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, total].map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeDasharray={t ? "3 5" : undefined} />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="axis-text">
              {t}
            </text>
          </g>
        ))}
        <text x={width - pad.right} y={y(total) - 6} textAnchor="end" className="axis-text">
          all {total} ready
        </text>
        {area && <path d={area} fill={`url(#g${gid})`} className="trend-area" />}
        {points.length > 1 && <path d={solid} fill="none" stroke="var(--brand)" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" className="trend-line" />}
        {projected && last >= 0 && (
          <path
            d={`M${x(last)},${y(points[last].ready)} L${x(all.length - 1)},${y(projected.ready)}`}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={3}
            strokeDasharray="6 7"
            strokeLinecap="round"
          />
        )}
        {all.map((p, i) => {
          const isPlan = projected && i === all.length - 1;
          return (
            <circle
              key={p.key}
              cx={x(i)}
              cy={y(p.ready)}
              r={i === shown ? 7 : 4.5}
              fill={isPlan ? "var(--accent)" : "var(--surface)"}
              stroke={isPlan ? "var(--accent)" : "var(--brand)"}
              strokeWidth={3}
              className="trend-dot"
            />
          );
        })}
        {all.map((p, i) =>
          i === 0 || i === all.length - 1 || all.length <= 6 ? (
            <text key={`l${p.key}`} x={x(i)} y={height - 10} textAnchor={i === 0 && all.length > 1 ? "start" : i === all.length - 1 && all.length > 1 ? "end" : "middle"} className="axis-text">
              {p.when}
            </text>
          ) : null,
        )}
      </svg>
      {sp && (
        <div
          className="chart-tip"
          style={{
            left: Math.min(Math.max(x(shown), 80), width - 80),
            top: Math.max(0, y(sp.ready) - 14),
            ["--arrow" as string]: `${x(shown) - Math.min(Math.max(x(shown), 80), width - 80)}px`,
          }}
          aria-hidden="true"
        >
          <strong>
            {sp.ready} of {sp.total} ready
          </strong>
          <span>{sp.label}</span>
        </div>
      )}
      <div className="bar-hits" role="group" aria-label="Readiness over time">
        {all.map((p, i) => (
          <button
            key={p.key}
            type="button"
            className="bar-hit"
            style={{ left: x(i) - 16, width: 32, top: pad.top - 8, height: plotH + 16 }}
            aria-label={`${p.when}: ${p.ready} of ${p.total} ready. ${p.label}`}
            onFocus={() => setFocus(i)}
            onBlur={() => setFocus(null)}
            onMouseEnter={() => setFocus(i)}
            onMouseLeave={() => setFocus(null)}
          />
        ))}
      </div>
    </div>
  );
}
