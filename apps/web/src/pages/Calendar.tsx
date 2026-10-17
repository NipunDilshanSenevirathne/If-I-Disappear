import { useMemo, useState } from "react";
import { CalendarMonth, monthsBetween } from "../components/charts/CalendarMonth";
import { PageHeader, Panel, Segmented, StateBadge } from "../components/ui";
import { fmtDay, fmtLong, fmtMonth } from "../lib/format";
import { EVENT } from "../lib/meta";
import { useLoaded } from "../state/app";

type Filter = "all" | "problems";

export default function Calendar() {
  const { h } = useLoaded();
  const a = h.analysis;
  const months = useMemo(() => (a ? monthsBetween(a.result.scenario.start, a.result.scenario.end_inclusive) : []), [a]);
  const [month, setMonth] = useState(0);
  const [day, setDay] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  if (!a) return null;
  const leaver = a.result.scenario.leaver_name;
  const events = a.result.timeline.filter((e) => filter === "all" || e.status !== "ready");
  const shownDay = day ? events.filter((e) => e.date === day) : [];
  const agenda = events.filter((e) => e.date.slice(0, 7) === months[month]);

  return (
    <>
      <PageHeader
        title="Calendar"
        lede={`Every date something has to happen while ${leaver} is away, from ${fmtDay(a.result.scenario.start)} to ${fmtDay(a.result.scenario.end_inclusive)}.`}
        actions={
          <Segmented
            label="Show"
            size="sm"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "Everything" },
              { value: "problems", label: "Only problems" },
            ]}
          />
        }
      />
      <div className="calendar-page">
        <Panel
          title={months[month] ? fmtMonth(`${months[month]}-01`) : ""}
          actions={
            months.length > 1 ? (
              <Segmented
                size="sm"
                label="Month"
                value={month}
                onChange={(m) => {
                  setMonth(m);
                  setDay(null);
                }}
                options={months.map((m, i) => ({ value: i, label: fmtMonth(`${m}-01`).split(" ")[0].slice(0, 3) }))}
              />
            ) : null
          }
        >
          {months[month] && (
            <CalendarMonth
              month={months[month]}
              events={events}
              start={a.result.scenario.start}
              endInclusive={a.result.scenario.end_inclusive}
              selected={day}
              onSelect={(d) => setDay(d === day ? null : d)}
            />
          )}
        </Panel>
        <Panel title={day ? fmtLong(day) : "This month"} eyebrow={day ? `${shownDay.length} due` : `${agenda.length} dates`}>
          {/* it scrolls, so it takes keyboard focus (arrow keys then scroll it) */}
          <ul className="agenda" tabIndex={0} aria-label={day ? `Due on ${fmtLong(day)}` : "Dates this month"}>
            {(day ? shownDay : agenda).map((e, i) => (
              <li key={`${e.date}-${e.responsibility}-${i}`}>
                <span className="agenda-date num">{fmtDay(e.date)}</span>
                <div className="agenda-main">
                  <strong>{e.responsibility_label}</strong>
                  <span className="small muted">{e.message ?? (e.person ? `${e.person} does it` : "")}</span>
                </div>
                <StateBadge state={EVENT[e.status]?.state ?? "not_due"} size="sm" />
              </li>
            ))}
            {(day ? shownDay : agenda).length === 0 && <li className="muted small">Nothing due.</li>}
          </ul>
        </Panel>
      </div>
    </>
  );
}
