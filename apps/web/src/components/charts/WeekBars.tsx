import { useMemo, useRef } from "react";
import { useWidth } from "./useSize";

export interface WeekDatum {
  key: string;
  label: string; // "9 Nov"
  sub: string; // "Week 2"
  ready: number;
  handover: number;
  unknown: number;
  blocked: number;
}

const LAYERS: { key: keyof Pick<WeekDatum, "ready" | "handover" | "unknown" | "blocked">; label: string; color: string }[] = [
  { key: "ready", label: "ready", color: "var(--st-prepared-fill)" },
  { key: "handover", label: "handover not finished", color: "var(--st-handover-fill)" },
  { key: "unknown", label: "need a check", color: "var(--st-confirm-fill)" },
  { key: "blocked", label: "blocked", color: "var(--st-blocked-fill)" },
];

function niceMax(n: number): number {
  if (n <= 4) return 4;
  if (n <= 6) return 6;
  if (n <= 8) return 8;
  if (n <= 10) return 10;
  return Math.ceil(n / 5) * 5;
}

export function describeWeek(w: WeekDatum): string {
  const total = w.ready + w.handover + w.unknown + w.blocked;
  if (!total) return `Week of ${w.label}: nothing due.`;
  const parts = LAYERS.filter((l) => w[l.key] > 0).map((l) => `${w[l.key]} ${l.label}`);
  return `Week of ${w.label}: ${total} due, ${parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0]}.`;
}

/** Stacked bars, one per week of the absence; the selected week is drawn in full
 *  colour with its numbers in a tooltip. Bars are keyboard-focusable buttons. */
export function WeekBars({ weeks, selected, onSelect, height = 280 }: { weeks: WeekDatum[]; selected: number; onSelect: (i: number) => void; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const pad = { top: 74, right: 8, bottom: 40, left: 28 }; // room above the bars for the tooltip
  const max = useMemo(() => niceMax(Math.max(1, ...weeks.map((w) => w.ready + w.handover + w.unknown + w.blocked))), [weeks]);
  const plotW = Math.max(10, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;
  const slot = plotW / Math.max(1, weeks.length);
  const barW = Math.max(8, Math.min(34, slot * 0.56));
  const y = (v: number) => pad.top + plotH - (v / max) * plotH;
  const ticks = [0, max / 2, max];
  const sel = weeks[selected];
  const selTotal = sel ? sel.ready + sel.handover + sel.unknown + sel.blocked : 0;
  const selX = pad.left + slot * selected + slot / 2;

  const onKey = (e: React.KeyboardEvent, i: number) => {
    let next = i;
    if (e.key === "ArrowRight") next = Math.min(weeks.length - 1, i + 1);
    else if (e.key === "ArrowLeft") next = Math.max(0, i - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = weeks.length - 1;
    else return;
    e.preventDefault();
    onSelect(next);
    buttons.current[next]?.focus();
  };

  return (
    <div className="weekbars" ref={ref} style={{ height }}>
      <svg width={width} height={height} aria-hidden="true">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeDasharray={t ? "3 5" : undefined} />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="axis-text">
              {Math.round(t)}
            </text>
          </g>
        ))}
        {weeks.map((w, i) => {
          const cx = pad.left + slot * i + slot / 2;
          let acc = 0;
          const on = i === selected;
          return (
            <g key={w.key} className={`bar ${on ? "on" : ""}`}>
              <rect x={cx - barW / 2} y={pad.top} width={barW} height={plotH} rx={barW / 2.4} fill="var(--surface-3)" opacity={on ? 0.9 : 0.5} />
              {LAYERS.map((l) => {
                const v = w[l.key];
                if (!v) return null;
                const y0 = y(acc + v);
                const h = Math.max(2, y(acc) - y0 - 1.5);
                acc += v;
                return <rect key={l.key} className="bar-seg" x={cx - barW / 2} y={y0} width={barW} height={h} rx={Math.min(6, barW / 3)} fill={l.color} opacity={on ? 1 : 0.42} />;
              })}
              <text x={cx} y={height - pad.bottom + 18} textAnchor="middle" className={`axis-text ${on ? "strong" : ""}`}>
                {w.label}
              </text>
            </g>
          );
        })}
      </svg>
      {sel && (
        <div
          className="chart-tip"
          style={{
            left: Math.min(Math.max(selX, 76), width - 76),
            top: Math.max(0, y(selTotal) - 12),
            ["--arrow" as string]: `${selX - Math.min(Math.max(selX, 76), width - 76)}px`,
          }}
          aria-hidden="true"
        >
          <strong>{sel.sub}</strong>
          <span>{selTotal ? `${selTotal} due` : "Nothing due"}</span>
          {sel.blocked > 0 && <span className="tip-bad">{sel.blocked} blocked</span>}
        </div>
      )}
      <div className="bar-hits" role="group" aria-label="Weeks of the absence">
        {weeks.map((w, i) => (
          <button
            key={w.key}
            ref={(el) => {
              buttons.current[i] = el;
            }}
            type="button"
            className="bar-hit"
            style={{ left: pad.left + slot * i, width: slot, top: pad.top, height: plotH + 26 }}
            aria-pressed={i === selected}
            aria-label={describeWeek(w)}
            tabIndex={i === selected ? 0 : -1}
            onClick={() => onSelect(i)}
            onMouseEnter={() => onSelect(i)}
            onKeyDown={(e) => onKey(e, i)}
          />
        ))}
      </div>
    </div>
  );
}
