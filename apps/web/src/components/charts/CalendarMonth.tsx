import { useMemo } from "react";
import { EVENT, STATE } from "../../lib/meta";
import { fmtLong } from "../../lib/format";
import type { TimelineEvent } from "../../lib/types";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function monthsBetween(start: string, endInclusive: string): string[] {
  const out: string[] = [];
  const d = new Date(`${start.slice(0, 7)}-01T00:00:00`);
  const last = endInclusive.slice(0, 7);
  while (iso(d).slice(0, 7) <= last) {
    out.push(iso(d).slice(0, 7));
    d.setMonth(d.getMonth() + 1);
  }
  return out;
}

/** A month of the absence with what happens each day, coloured by status. */
export function CalendarMonth({
  month,
  events,
  start,
  endInclusive,
  selected,
  onSelect,
  compact = false,
}: {
  month: string; // YYYY-MM
  events: TimelineEvent[];
  start: string;
  endInclusive: string;
  selected: string | null;
  onSelect: (day: string) => void;
  compact?: boolean;
}) {
  const byDay = useMemo(() => {
    const m = new Map<string, TimelineEvent[]>();
    for (const e of events) m.set(e.date, [...(m.get(e.date) ?? []), e]);
    return m;
  }, [events]);
  const cells = useMemo(() => {
    const first = new Date(`${month}-01T00:00:00`);
    const offset = (first.getDay() + 6) % 7; // Monday first
    const days: (string | null)[] = Array.from({ length: offset }, () => null);
    const d = new Date(first);
    while (iso(d).slice(0, 7) === month) {
      days.push(iso(d));
      d.setDate(d.getDate() + 1);
    }
    while (days.length % 7) days.push(null);
    return days;
  }, [month]);

  return (
    <div className={`calendar ${compact ? "compact" : ""}`} role="grid" aria-label={`Calendar for ${new Date(`${month}-01T00:00:00`).toLocaleString("en-GB", { month: "long", year: "numeric" })}`}>
      <div className="cal-row cal-head" role="row">
        {WEEKDAYS.map((w) => (
          <span key={w} role="columnheader" className="cal-wd">
            {w}
          </span>
        ))}
      </div>
      {Array.from({ length: cells.length / 7 }, (_, r) => (
        <div className="cal-row" role="row" key={r}>
          {cells.slice(r * 7, r * 7 + 7).map((day, c) => {
            if (!day) return <span key={c} className="cal-cell blank" role="gridcell" />;
            const evs = byDay.get(day) ?? [];
            const inside = day >= start && day <= endInclusive;
            const worst = evs.reduce<string | null>((acc, e) => {
              const order = ["blocked", "unknown", "handover", "ready"];
              return acc === null || order.indexOf(e.status) < order.indexOf(acc) ? e.status : acc;
            }, null);
            const label = `${fmtLong(day)}${day === start ? ", leaves" : ""}${day === endInclusive ? ", last day away" : ""}: ${
              evs.length ? evs.map((e) => `${e.responsibility_label}, ${EVENT[e.status]?.label ?? e.status}`).join("; ") : "nothing due"
            }`;
            return (
              <button
                key={day}
                type="button"
                role="gridcell"
                className={`cal-cell ${inside ? "inside" : ""} ${selected === day ? "on" : ""} ${worst ? `has-${worst}` : ""} ${day === start ? "start" : ""}`}
                aria-label={label}
                aria-selected={selected === day}
                onClick={() => onSelect(day)}
              >
                <span className="cal-num num">{Number(day.slice(8))}</span>
                {day === start && <span className="cal-flag">Leaves</span>}
                {day === endInclusive && <span className="cal-flag end">Last day</span>}
                {!compact &&
                  evs.slice(0, 2).map((e, i) => {
                    const st = STATE[EVENT[e.status]?.state ?? "not_due"];
                    return (
                      <span key={i} className="cal-chip" style={{ background: st.soft, color: st.color }}>
                        <i style={{ background: st.fill }} aria-hidden="true" />
                        {e.responsibility_label}
                      </span>
                    );
                  })}
                {!compact && evs.length > 2 && <span className="cal-more">+{evs.length - 2} more</span>}
                {evs.length > 0 && (
                  <span className="cal-dots" aria-hidden="true">
                    {evs.slice(0, 4).map((e, i) => (
                      <i key={i} style={{ background: STATE[EVENT[e.status]?.state ?? "not_due"].fill }} />
                    ))}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
