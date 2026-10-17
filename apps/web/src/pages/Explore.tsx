import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, RotateCcw, Telescope, UserMinus, Unplug } from "lucide-react";
import { Avatar, ErrorNote, PageHeader, Panel, Spinner, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { STATE } from "../lib/meta";
import type { ExploreOptions, ExploreResult, State, Summary } from "../lib/types";
import { useLoaded } from "../state/app";

function StackBar({ s, label }: { s: Summary; label: string }) {
  const parts: { key: State; v: number }[] = [
    { key: "prepared", v: s.prepared + s.not_due },
    { key: "needs_handover", v: s.needs_handover },
    { key: "needs_confirmation", v: s.needs_confirmation },
    { key: "blocked", v: s.blocked },
  ];
  return (
    <div className="stackbar-row">
      <span className="stackbar-label">{label}</span>
      <div className="stackbar" role="img" aria-label={`${label}: ${s.ready} of ${s.total} ready, ${s.blocked} blocked`}>
        {parts.map((p) =>
          p.v ? (
            <span key={p.key} style={{ flexGrow: p.v, background: STATE[p.key].fill }} title={`${STATE[p.key].label}: ${p.v}`}>
              {p.v}
            </span>
          ) : null,
        )}
      </div>
      <strong className="num stackbar-ready">
        {s.ready}/{s.total}
      </strong>
    </div>
  );
}

export default function Explore() {
  const { h } = useLoaded();
  const [opts, setOpts] = useState<ExploreOptions | null>(null);
  const [away, setAway] = useState<string[]>([]);
  const [off, setOff] = useState<string[]>([]);
  const [keep, setKeep] = useState<string[]>([]);
  const [days, setDays] = useState<number | null>(null);
  const [result, setResult] = useState<ExploreResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    api.exploreOptions(h.id).then(setOpts, (e) => setError(errorText(e)));
  }, [h.id, h.rev]);

  useEffect(() => {
    if (!opts) return;
    const n = ++seq.current;
    setBusy(true);
    const t = window.setTimeout(() => {
      api
        .explore(h.id, { also_away: away, unavailable: off, keep_using: keep, days })
        .then(
          (r) => n === seq.current && (setResult(r), setError(null)),
          (e) => n === seq.current && setError(errorText(e)),
        )
        .finally(() => n === seq.current && setBusy(false));
    }, 220);
    return () => window.clearTimeout(t);
  }, [opts, away, off, keep, days, h.id, h.rev]);

  const toggle = (list: string[], set: (v: string[]) => void, id: string) => set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const changedRows = useMemo(() => (result?.responsibilities ?? []).filter((r) => r.changed), [result]);
  const leaver = h.people.find((p) => p.id === h.settings.leaver)?.name ?? "The person leaving";
  const dirty = away.length + off.length + keep.length > 0 || days !== null;

  return (
    <>
      <PageHeader
        title="Explore: what if…?"
        lede={`Change one thing and see what would happen while ${leaver} is away. The same engine recomputes every date. Nothing is saved, and no AI is used, so it's instant.`}
      />
      {error && <ErrorNote message={error} />}
      {!opts ? (
        <Spinner label="Loading…" />
      ) : (
        <div className="explore">
          <Panel className="explore-controls" tour="explore-controls" title="Change something" tone="glass">
            <fieldset className="choice-group">
              <legend>
                <UserMinus size={16} aria-hidden="true" /> Who else is away?
              </legend>
              <div className="chips">
                {opts.people.map((p) => (
                  <button key={p.id} type="button" className={`choice ${away.includes(p.id) ? "on" : ""}`} aria-pressed={away.includes(p.id)} onClick={() => toggle(away, setAway, p.id)}>
                    <Avatar id={p.id} name={p.name} size={22} /> {p.name}
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset className="choice-group">
              <legend>
                <Unplug size={16} aria-hidden="true" /> What isn't there?
              </legend>
              <div className="chips">
                {opts.things.map((t) => (
                  <button key={t.id} type="button" className={`choice ${off.includes(t.id) ? "on" : ""}`} aria-pressed={off.includes(t.id)} onClick={() => toggle(off, setOff, t.id)}>
                    {t.name}
                  </button>
                ))}
              </div>
            </fieldset>
            {opts.assumptions.length > 0 && (
              <fieldset className="choice-group">
                <legend>What the family decided</legend>
                <div className="chips">
                  {opts.assumptions.map((a) => (
                    <button key={a.id} type="button" className={`choice ${keep.includes(a.id) ? "on" : ""}`} aria-pressed={keep.includes(a.id)} onClick={() => toggle(keep, setKeep, a.id)}>
                      Undo: {a.label}
                    </button>
                  ))}
                </div>
              </fieldset>
            )}
            <fieldset className="choice-group">
              <legend>How long away?</legend>
              <div className="range-row">
                <input
                  type="range"
                  min={7}
                  max={180}
                  step={1}
                  value={days ?? opts.days}
                  aria-label="Days away"
                  onChange={(e) => setDays(Number(e.target.value) === opts.days ? null : Number(e.target.value))}
                />
                <strong className="num">{days ?? opts.days} days</strong>
              </div>
            </fieldset>
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              disabled={!dirty}
              onClick={() => {
                setAway([]);
                setOff([]);
                setKeep([]);
                setDays(null);
              }}
            >
              <RotateCcw size={14} aria-hidden="true" /> Back to what's recorded
            </button>
          </Panel>

          <div className="explore-result" aria-live="polite" aria-busy={busy}>
            {result && (
              <>
                <Panel title={dirty ? "With these changes" : "As recorded"} eyebrow={busy ? "Recomputing…" : `${result.scenario.days} days from the departure`} actions={busy ? <Spinner /> : <span className="tag live-tag">Instant</span>}>
                  <div className="compare">
                    <div className="compare-big">
                      <span className="compare-num num">{result.before.ready}</span>
                      <span className="faint small">ready as recorded</span>
                    </div>
                    <ArrowRight size={26} className="faint" aria-hidden="true" />
                    <div className={`compare-big ${result.after.ready < result.before.ready ? "worse" : result.after.ready > result.before.ready ? "better" : ""}`}>
                      <span className="compare-num num">{result.after.ready}</span>
                      <span className="faint small">ready if this happens</span>
                    </div>
                    <span className="compare-total faint small num">of {result.after.total}</span>
                  </div>
                  <StackBar s={result.before} label="Recorded" />
                  <StackBar s={result.after} label="What if" />
                  {result.changes.length > 0 ? (
                    <p className="small muted">Changed: {result.changes.join(" · ")}.</p>
                  ) : (
                    <p className="small muted">Pick something on the left to see what would change.</p>
                  )}
                </Panel>
                <Panel title={changedRows.length ? `${changedRows.length} would change` : "Nothing would change"} eyebrow={`${result.worse} worse · ${result.better} better`}>
                  <ul className="explore-list">
                    {result.responsibilities.map((r) => (
                      <li key={r.id} className={r.changed ? (r.worse ? "worse" : "better") : ""}>
                        <div className="explore-line">
                          <strong>{r.label}</strong>
                          <span className="explore-states">
                            {r.before && <StateBadge state={r.before} size="sm" />}
                            {r.changed && (
                              <>
                                <ArrowRight size={14} aria-hidden="true" />
                                <StateBadge state={r.after} size="sm" />
                              </>
                            )}
                          </span>
                        </div>
                        {r.changed && <p className="small muted">{r.headline}</p>}
                      </li>
                    ))}
                  </ul>
                </Panel>
              </>
            )}
            {!result && !error && (
              <Panel>
                <div className="empty">
                  <Telescope size={26} aria-hidden="true" />
                  <Spinner label="Working it out…" />
                </div>
              </Panel>
            )}
          </div>
        </div>
      )}
    </>
  );
}
