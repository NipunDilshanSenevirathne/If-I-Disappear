import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AudioLines, PencilLine } from "lucide-react";
import { PracticeSession } from "../components/PracticeSession";
import { StepsEditor } from "../components/StepsEditor";
import { EmptyState, Field, PageHeader, Panel, Spinner, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { cap, fmtDate } from "../lib/format";
import { RESULT } from "../lib/meta";
import type { PracticeBrief } from "../lib/types";
import { useLoaded, useToast } from "../state/app";

export default function Practice() {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const results = h.analysis?.result.responsibilities ?? [];
  const withSteps = new Set(h.procedures.map((p) => p.responsibility));
  const tasks = h.entities.filter((e) => e.kind === "responsibility").map((e) => e.id);
  const open = (r: string) => results.find((x) => x.id === r && x.state !== "prepared");
  const adults = h.people.filter((p) => !p.minor && p.id !== h.settings.leaver);
  const responsibility =
    params.get("r") ?? tasks.find((r) => withSteps.has(r) && open(r)) ?? tasks.find((r) => withSteps.has(r)) ?? tasks.find(open) ?? tasks[0] ?? "";
  const person = params.get("p") ?? adults.find((p) => p.role === "backup")?.id ?? adults[0]?.id ?? "";
  const hasSteps = withSteps.has(responsibility);
  const stepsVersion = h.procedures.find((p) => p.responsibility === responsibility)?.version ?? 0;
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState<PracticeBrief | null>(null);
  const [session, setSession] = useState(0);

  // keep the task and person in the address once chosen, so a live update elsewhere
  // (which can change which task is "first") never swaps the task mid-explanation
  useEffect(() => {
    if (responsibility && person && (params.get("r") !== responsibility || params.get("p") !== person)) setParams({ r: responsibility, p: person }, { replace: true });
  }, [responsibility, person]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setBrief(null);
    if (!responsibility || !person || !hasSteps || editing) return;
    api.practice(h.id, responsibility, person).then(setBrief, (e) => toast(errorText(e), "error"));
  }, [h.id, responsibility, person, hasSteps, editing, stepsVersion, toast]);

  const name = (id: string) => h.entities.find((e) => e.id === id)?.name ?? id;
  const state = results.find((r) => r.id === responsibility)?.state;

  if (tasks.length === 0)
    return (
      <>
        <PageHeader title="Practise" lede="The person staying explains a task in their own words. If they need a hint, it counts as practised with help." />
        <EmptyState icon={<AudioLines size={28} />} title="There are no tasks yet" action={<Link to={`/h/${h.id}/capture`} className="btn btn-primary">Add the first one</Link>}>
          Record a voice note or add a task by hand first.
        </EmptyState>
      </>
    );

  return (
    <>
      <PageHeader title="Practise" lede="The person staying explains a task in their own words, by talking or typing. If they need a hint, it counts as practised with help." />
      <div className="practice-page">
        <div className="practice-main">
          <Panel tone="glass" tour="practice-start">
            <div className="grid-2">
              <Field label="Task">
                <select
                  className="input"
                  value={responsibility}
                  onChange={(e) => {
                    setEditing(false);
                    setSession((n) => n + 1);
                    setParams({ r: e.target.value, p: person });
                  }}
                >
                  {tasks.map((r) => (
                    <option key={r} value={r}>
                      {cap(name(r))}
                      {withSteps.has(r) ? "" : " (no steps yet)"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Who is practising">
                <select
                  className="input"
                  value={person}
                  onChange={(e) => {
                    setSession((n) => n + 1);
                    setParams({ r: responsibility, p: e.target.value });
                  }}
                >
                  {adults.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {state && (
              <div className="row small">
                <span className="muted">This task now:</span>
                <StateBadge state={state} size="sm" />
              </div>
            )}
          </Panel>

          {hasSteps && !editing ? (
            brief ? (
              <Panel>
                <PracticeSession
                  key={`${responsibility}-${person}-${session}-${stepsVersion}`}
                  scenario={brief.scenario}
                  steps={brief.steps}
                  personName={brief.person_name}
                  liveVoice={brief.live_voice}
                  grade={async (body) => {
                    const out = await api.attempt(h.id, responsibility, { person, ...body });
                    setHousehold(out.household);
                    // show the new attempt in "Earlier attempts" straight away
                    api.practice(h.id, responsibility, person).then(setBrief, () => undefined);
                    return out;
                  }}
                  voiceToken={() => api.liveToken(h.id, responsibility, person)}
                />
              </Panel>
            ) : (
              <Spinner label="Loading the task…" />
            )
          ) : responsibility ? (
            <StepsEditor
              hid={h.id}
              responsibility={responsibility}
              onSaved={(next) => {
                setHousehold(next);
                setEditing(false);
              }}
              onCancel={hasSteps ? () => setEditing(false) : undefined}
            />
          ) : null}
        </div>

        <aside className="practice-side">
          {hasSteps && !editing && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>
              <PencilLine size={15} aria-hidden="true" /> Edit the steps
            </button>
          )}
          <Panel title="Earlier attempts" eyebrow={brief ? `${brief.attempts.length} so far` : undefined}>
            {brief && brief.attempts.length > 0 ? (
              <ul className="attempts">
                {brief.attempts
                  .slice()
                  .reverse()
                  .slice(0, 8)
                  .map((a) => (
                    <li key={a.id}>
                      <StateBadge state={RESULT[a.result]?.tone ?? "needs_confirmation"} size="sm" label={RESULT[a.result]?.label} />
                      <span className="tiny faint">
                        {a.created ? fmtDate(a.created) : ""} · {a.grader === "keyword" ? "offline checker" : a.grader}
                      </span>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="small muted">No attempts yet.</p>
            )}
          </Panel>
          <Panel title="How it's checked" tone="flat">
            <p className="small muted">
              The approved steps stay hidden while the person explains. A model marks each step and points at the words that cover it; code then decides the result. A key step that isn't covered
              means "Not yet", and any hint means "with help".
            </p>
          </Panel>
        </aside>
      </div>
    </>
  );
}
