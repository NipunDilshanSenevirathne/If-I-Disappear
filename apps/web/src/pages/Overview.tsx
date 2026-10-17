import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertOctagon,
  ArrowRight,
  CircleHelp,
  Clock3,
  Gauge,
  ListChecks,
  Mic,
  PencilLine,
  RefreshCw,
  ScanText,
  Sparkles,
} from "lucide-react";
import { BoardingPass, FindingMini, KpiTile, RespDetail, RespRow } from "../components/household";
import { CalendarMonth, monthsBetween } from "../components/charts/CalendarMonth";
import { Donut, Legend } from "../components/charts/Donut";
import { TrendChart } from "../components/charts/TrendChart";
import { describeWeek, WeekBars } from "../components/charts/WeekBars";
import { householdTour, TOUR_SEEN, useTour } from "../components/tour/Tour";
import { JobProgress, Modal, Panel, Segmented } from "../components/ui";
import { api, errorText, waitForJob } from "../lib/api";
import { daysUntil, stateSlices, trendPoints, weeksOf, worstWeek } from "../lib/derive";
import { fmtAgo, fmtDay, fmtLong, fmtMonth, todayIso } from "../lib/format";
import { readLocal } from "../lib/hooks";
import { EVENT, STATE } from "../lib/meta";
import type { RespResult, TraceStep } from "../lib/types";
import { useLoaded, useToast, useUsage } from "../state/app";

export default function Overview() {
  const { h, refresh, pulse } = useLoaded();
  const toast = useToast();
  const tour = useTour();
  const usage = useUsage();
  const base = `/h/${h.id}`;
  const a = h.analysis;
  const leaver = h.people.find((p) => p.id === h.settings.leaver)?.name ?? "The person leaving";
  const [detail, setDetail] = useState<RespResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [showJob, setShowJob] = useState(false);

  const weeks = useMemo(() => (a ? weeksOf(a) : []), [a]);
  const [week, setWeek] = useState(() => (a ? worstWeek(weeksOf(a)) : 0));
  useEffect(() => {
    if (week >= weeks.length) setWeek(0);
  }, [weeks.length, week]);

  const months = useMemo(() => (a ? monthsBetween(a.result.scenario.start, a.result.scenario.end_inclusive) : []), [a]);
  const [month, setMonth] = useState(0);
  const [day, setDay] = useState<string | null>(null);

  // start the tour when asked (?tour=1), or the first time someone opens a sample household
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const asked = params.get("tour") === "1";
    if (asked) setParams({}, { replace: true });
    if ((asked || (h.demo && !readLocal(TOUR_SEEN))) && !tour.active) {
      const t = window.setTimeout(() => tour.start(householdTour(leaver, h.demo), base), 900);
      return () => window.clearTimeout(t);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const checkAgain = async () => {
    setChecking(true);
    setSteps([]);
    setShowJob(true);
    try {
      const { job } = await api.analyze(h.id);
      const done = await waitForJob(job.id, (j) => setSteps(j.progress));
      setSteps(done.progress);
      if (done.status === "error") toast(done.error ?? "The check didn't finish.", "error");
      await refresh();
      usage.refresh();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setChecking(false);
    }
  };

  if (!a || a.result.summary.total === 0) return <GettingStarted />;

  const s = a.result.summary;
  const today = h.demo ? h.settings.assessment_date : todayIso();
  const until = daysUntil(h.settings.departure, today);
  const slices = stateSlices(s);
  const history = h.history;
  const prev = history.length > 1 ? history[history.length - 2] : null;
  const plan = a.plan;
  const urgent = a.findings.slice(0, 3);
  const results = a.result.responsibilities;
  const dayEvents = day ? a.result.timeline.filter((e) => e.date === day) : [];
  const leavesText = until > 1 ? `leaves in ${until} days.` : until === 1 ? "leaves tomorrow." : until === 0 ? "leaves today." : `left on ${fmtDay(h.settings.departure)}.`;

  return (
    <div className="overview">
      <section className="ov-hero" data-tour="hero">
        <div className="ov-hero-text">
          <span className="eyebrow-chip">
            <span className={`live-dot ${pulse ? "flash" : ""}`} aria-hidden="true" /> Live · checked {fmtAgo(a.computed_at)}
          </span>
          <h1 className="two-tone ov-title">
            <span>
              {leaver} {leavesText}
            </span>{" "}
            <span className="second">
              {s.ready} of {s.total} things are ready.
            </span>
          </h1>
          <p className="lede">
            This is what happens at home during the {a.result.scenario.days} days, worked out from what the family recorded. It updates by itself when something changes.
          </p>
          <div className="row ov-actions">
            <Link to={`${base}/plan`} className="btn btn-primary">
              <ListChecks size={17} aria-hidden="true" /> Open the plan ({plan.minutes} min)
            </Link>
            <button type="button" className="btn btn-ghost" onClick={() => void checkAgain()} disabled={checking}>
              <RefreshCw size={16} className={checking ? "spin" : ""} aria-hidden="true" /> {checking ? "Checking…" : "Check again with AI"}
            </button>
          </div>
          {h.demo && <p className="tiny faint">Sample household. Every name, number and document here is made up.</p>}
        </div>
        <BoardingPass h={h} />
      </section>

      <section className="kpis" data-tour="kpis" aria-label="Readiness in numbers">
        <KpiTile
          label="Ready"
          value={
            <>
              {s.ready}
              <span className="kpi-of">/{s.total}</span>
            </>
          }
          sub={`ready for all ${a.result.scenario.days} days`}
          icon={<Gauge size={18} aria-hidden="true" />}
          tone="prepared"
          spark={history.map((p) => p.ready)}
          delta={prev ? s.ready - prev.ready : null}
        />
        <KpiTile
          label="Blocked"
          value={s.blocked}
          sub={s.blocked ? "will stop on a date while away" : "nothing will stop"}
          icon={<AlertOctagon size={18} aria-hidden="true" />}
          tone="blocked"
          spark={history.map((p) => p.blocked)}
          delta={prev ? -(s.blocked - prev.blocked) : null}
          to={`${base}/found`}
        />
        <KpiTile
          label="Needs a check"
          value={s.needs_confirmation + s.needs_handover}
          sub={`${s.needs_confirmation} unknown · ${s.needs_handover} handover not finished`}
          icon={<CircleHelp size={18} aria-hidden="true" />}
          tone="needs_confirmation"
          spark={history.map((p) => p.needs_confirmation + p.needs_handover)}
          to={`${base}/found`}
        />
        <KpiTile
          label="The plan"
          value={
            <>
              {plan.minutes}
              <span className="kpi-of"> min</span>
            </>
          }
          sub={`gets ${plan.after.ready} of ${plan.after.total} ready`}
          icon={<Clock3 size={18} aria-hidden="true" />}
          tone="accent"
          to={`${base}/plan`}
        />
      </section>

      <div className="ov-grid">
        <Panel
          className="span-8"
          tour="weeks"
          title="Across the absence"
          eyebrow={`${weeks.length} weeks · ${a.result.timeline.length} dates`}
          actions={<span className="tag live-tag">Live</span>}
        >
          <WeekBars weeks={weeks} selected={Math.min(week, weeks.length - 1)} onSelect={setWeek} />
          <p className="chart-caption" aria-live="polite">
            {weeks[week] ? describeWeek(weeks[week]) : ""}
          </p>
          <div className="chart-key" aria-hidden="true">
            {(["prepared", "needs_handover", "needs_confirmation", "blocked"] as const).map((k) => (
              <span key={k}>
                <i style={{ background: STATE[k].fill }} /> {STATE[k].label}
              </span>
            ))}
          </div>
        </Panel>

        <Panel className="span-4" title="Where things stand" eyebrow={`${s.total} responsibilities`}>
          <div className="donut-wrap">
            <Donut
              slices={slices}
              label={`${s.ready} of ${s.total} responsibilities ready`}
              center={
                <>
                  <strong className="num">{s.ready}</strong>
                  <span>of {s.total} ready</span>
                </>
              }
            />
            <Legend slices={slices} total={s.total} />
          </div>
          {s.ready_pct != null && <p className="tiny faint">Weighted by importance: {s.ready_pct}% ready.</p>}
        </Panel>

        <Panel
          className="span-7"
          title="Responsibilities"
          eyebrow="Sorted by what bites first"
          actions={
            <Link to={`${base}/capture`} className="btn btn-quiet btn-sm">
              <PencilLine size={14} aria-hidden="true" /> Add
            </Link>
          }
        >
          <ul className="resp-list">
            {results.map((r) => (
              <RespRow key={r.id} r={r} onOpen={setDetail} />
            ))}
          </ul>
        </Panel>

        <Panel
          className="span-5"
          tour="urgent"
          title="Most urgent"
          eyebrow={`${a.findings.length} found`}
          actions={
            <Link to={`${base}/found`} className="btn btn-quiet btn-sm">
              See all <ArrowRight size={14} aria-hidden="true" />
            </Link>
          }
        >
          {urgent.length ? (
            <ul className="finding-minis">
              {urgent.map((f) => (
                <FindingMini key={f.id} f={f} base={base} />
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing found. Either everything works, or nothing has been recorded yet.</p>
          )}
        </Panel>

        <Panel
          className="span-7"
          title="Calendar"
          eyebrow="Every date something has to happen"
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
              compact
              month={months[month]}
              events={a.result.timeline}
              start={a.result.scenario.start}
              endInclusive={a.result.scenario.end_inclusive}
              selected={day}
              onSelect={(d) => setDay(d === day ? null : d)}
            />
          )}
          <div className="day-detail" aria-live="polite">
            {day ? (
              <>
                <strong>{fmtLong(day)}</strong>
                {dayEvents.length ? (
                  <ul>
                    {dayEvents.map((e, i) => {
                      const st = STATE[EVENT[e.status]?.state ?? "not_due"];
                      return (
                        <li key={i}>
                          <i style={{ background: st.fill }} aria-hidden="true" />
                          <span>
                            {e.responsibility_label}: <span className="muted">{e.message ?? EVENT[e.status]?.label}</span>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <span className="muted small"> Nothing due.</span>
                )}
              </>
            ) : (
              <span className="muted small">Pick a day to see what happens.</span>
            )}
            <Link to={`${base}/calendar`} className="btn btn-quiet btn-sm">
              Full calendar <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>
        </Panel>

        <Panel className="span-5" title="Readiness over time" eyebrow="After each change, and with the plan" actions={<span className="tag live-tag">Live</span>}>
          <TrendChart points={trendPoints(history)} projected={{ ready: plan.after.ready, label: `If the plan is done (${plan.minutes} min)` }} />
          <p className="tiny faint">Solid: what's recorded. Dashed: where the current plan would take it. Nothing counts until it's recorded as done.</p>
        </Panel>
      </div>

      <RespDetail r={detail} onClose={() => setDetail(null)} base={base} />
      <Modal open={showJob} onClose={() => setShowJob(false)} title={checking ? "Checking again with AI…" : "Check finished"}>
        <p className="small muted">
          The engine recomputes everything, then a second AI reader reviews each finding. The AI can uphold, narrow or question a finding; it can't change a number.
        </p>
        <JobProgress steps={steps} running={checking} />
        {!checking && (
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={() => setShowJob(false)}>
              Done
            </button>
            <Link to={`${base}/trace`} className="btn btn-ghost">
              How it was worked out
            </Link>
          </div>
        )}
      </Modal>
    </div>
  );
}

function GettingStarted() {
  const { h } = useLoaded();
  const base = `/h/${h.id}`;
  const leaver = h.people.find((p) => p.id === h.settings.leaver)?.name ?? "The person leaving";
  return (
    <div className="overview">
      <section className="ov-hero" data-tour="hero">
        <div className="ov-hero-text">
          <span className="eyebrow-chip">
            <Sparkles size={14} aria-hidden="true" /> New household
          </span>
          <h1 className="two-tone ov-title">
            <span>Let's find out what stops</span> <span className="second">while {leaver} is away.</span>
          </h1>
          <p className="lede">Tell it how the house runs. Talk, take photos, or type. Every fact is shown to you before it's used.</p>
        </div>
        <BoardingPass h={h} />
      </section>
      <ol className="start-steps">
        <li>
          <Link to={`${base}/capture`} className="start-step">
            <span className="start-num num">1</span>
            <Mic size={22} aria-hidden="true" />
            <strong>Record a voice note</strong>
            <span className="muted small">"On the 10th I pay the electricity bill on the bank app…" Talk for a minute about a normal month.</span>
          </Link>
        </li>
        <li>
          <Link to={`${base}/review`} className="start-step">
            <span className="start-num num">2</span>
            <ScanText size={22} aria-hidden="true" />
            <strong>Check the facts</strong>
            <span className="muted small">Each fact shows the exact words it came from. Accept the right ones.</span>
          </Link>
        </li>
        <li>
          <Link to={`${base}/capture?mode=form`} className="start-step">
            <span className="start-num num">3</span>
            <PencilLine size={22} aria-hidden="true" />
            <strong>Or add a task by hand</strong>
            <span className="muted small">A short form, no AI needed. Useful when you'd rather type.</span>
          </Link>
        </li>
      </ol>
    </div>
  );
}
