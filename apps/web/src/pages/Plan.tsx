import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, AudioLines, CheckCircle2, ChevronDown, CircleDashed, Clock3, Sparkles } from "lucide-react";
import { Ring } from "../components/charts/Small";
import { Avatar, EmptyState, Field, Modal, PageHeader, Panel, Segmented, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { cap, fmtDay, minutes } from "../lib/format";
import { actionLabel, EVIDENCE_KINDS, RESULT } from "../lib/meta";
import type { Bundle, PlanView, Step } from "../lib/types";
import { useLoaded, useToast } from "../state/app";

const BUDGETS = [30, 60, 90, 120];

export default function Plan() {
  const { h } = useLoaded();
  const toast = useToast();
  const [budget, setBudget] = useState(h.settings.budget_minutes);
  const [plan, setPlan] = useState<PlanView | null>(h.analysis?.plan ?? null);
  const [step, setStep] = useState<Step | null>(null);

  useEffect(() => {
    if (budget === h.settings.budget_minutes) {
      setPlan(h.analysis?.plan ?? null);
      return;
    }
    api.plan(h.id, budget).then(setPlan, (e) => toast(errorText(e), "error"));
  }, [budget, h.analysis, h.id, h.settings.budget_minutes, toast]);

  const done = h.log.filter((l) => l.action === "evidence.record" || l.action === "practice.attempt").reverse();
  const nameOf = (id: string) => h.entities.find((e) => e.id === id)?.name ?? id;
  if (!plan) return null;
  const maxPerson = Math.max(1, ...plan.minutes_by_person.map((p) => p.minutes));
  const gain = plan.after.ready - plan.before.ready;

  return (
    <>
      <PageHeader
        title="Plan"
        lede="The fewest steps that do the most in the time you have. A step changes nothing until you record that it's done."
        tour="plan-budget"
        actions={
          <Segmented
            label="Time you have"
            value={budget}
            onChange={setBudget}
            options={BUDGETS.map((b) => ({ value: b, label: minutes(b) }))}
          />
        }
      />
      <div className="plan-top">
        <Panel tone="glass" className="plan-summary">
          <div className="plan-headline">
            <Ring value={plan.after.ready} max={plan.after.total} size={92} stroke={10} color="var(--st-prepared-fill)" label={`${plan.after.ready} of ${plan.after.total} ready after the plan`} />
            <div>
              <span className="eyebrow">With this plan</span>
              <p className="plan-big">
                <span className="num">{plan.before.ready}</span>
                <ArrowRight size={24} aria-hidden="true" />
                <span className="num">{plan.after.ready}</span>
                <span className="faint plan-of">of {plan.after.total} ready</span>
              </p>
              <p className="small muted">
                {gain > 0 ? `+${gain} in ` : "In "}
                <strong>{minutes(plan.minutes)}</strong> of work, shared between {plan.minutes_by_person.length} {plan.minutes_by_person.length === 1 ? "person" : "people"}.
              </p>
            </div>
          </div>
          <ul className="per-person">
            {plan.minutes_by_person.map((p) => (
              <li key={p.id}>
                <Avatar id={p.id} name={p.name} size={26} />
                <span className="pp-name">{p.name}</span>
                <span className="pp-bar">
                  <span style={{ width: `${(100 * p.minutes) / maxPerson}%` }} />
                </span>
                <span className="num small">{minutes(p.minutes)}</span>
              </li>
            ))}
          </ul>
          <p className="tiny faint">
            {plan.exhaustive ? `Every combination of the options was checked (${plan.evaluated}).` : "Too many options to check every combination; this is the best plan found."} Planned
            changes are hypothetical until evidence is recorded.
          </p>
        </Panel>
        <Panel title="Done so far" eyebrow={`${done.length} recorded`}>
          {done.length === 0 && <p className="small muted">Nothing recorded yet. Mark a step done when it really is.</p>}
          <ul className="done-list">
            {done.slice(0, 10).map((l, i) => (
              <li key={`${l.at}-${i}`}>
                <CheckCircle2 size={17} aria-hidden="true" />
                <span className="small">
                  {l.action === "practice.attempt"
                    ? `${nameOf(String(l.detail.person ?? ""))}: ${RESULT[String(l.detail.result)]?.label ?? l.detail.result} (${nameOf(String(l.detail.responsibility ?? ""))})`
                    : ((l.detail.changes as string[] | undefined) ?? []).join(" ") || actionLabel(l.action)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="bundles" data-tour="plan-steps">
        {plan.bundles.length === 0 && (
          <EmptyState icon={<Sparkles size={26} />} title="Nothing left to plan">
            Everything that can be fixed in this time is fixed. Try more time, or look at what's still open.
          </EmptyState>
        )}
        {plan.bundles.map((b) => (
          <BundleCard key={b.id} b={b} plan={plan} onStep={setStep} />
        ))}
      </div>

      {plan.alternatives.length > 0 && <Alternatives items={plan.alternatives} />}
      <EvidenceDialog step={step} onClose={() => setStep(null)} />
    </>
  );
}

function Alternatives({ items }: { items: Bundle[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Panel tone="flat">
      <button type="button" className="disclose" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <ChevronDown size={16} aria-hidden="true" /> Other ways to do it ({items.length})
      </button>
      {open && (
        <div className="alt-list">
          {items.map((b) => (
            <div key={b.id} className="alt">
              <strong>
                {cap(b.responsibility_label)}: {b.label}
              </strong>
              <span className="small muted">{minutes(b.minutes)}</span>
              <ul>
                {b.steps.map((s) => (
                  <li key={s.id} className="small">
                    {cap(s.title)} <span className="faint">({s.owner_name}, {minutes(s.minutes)})</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function BundleCard({ b, plan, onStep }: { b: Bundle; plan: PlanView; onStep: (s: Step) => void }) {
  const { h } = useLoaded();
  const after = plan.after_states[b.responsibility];
  const before = h.analysis?.result.responsibilities.find((r) => r.id === b.responsibility)?.state;
  return (
    <article className="bundle">
      <header className="bundle-head">
        <div>
          <h2>{cap(b.responsibility_label)}</h2>
          <span className="small muted">
            {b.label} · <Clock3 size={13} aria-hidden="true" style={{ display: "inline", verticalAlign: "-2px" }} /> {minutes(b.minutes)}
          </span>
        </div>
        <span className="bundle-states">
          {before && <StateBadge state={before} size="sm" />}
          {after && (
            <>
              <ArrowRight size={14} aria-hidden="true" />
              <StateBadge state={after.state} size="sm" />
            </>
          )}
        </span>
      </header>
      {b.leaves.length > 0 && <p className="tiny warn-text">Still open after this: {b.leaves.map(fmtDay).join(", ")}</p>}
      <ol className="steps">
        {b.steps.map((s) => (
          <li key={s.id} className="step">
            <Avatar id={s.owner} name={s.owner_name} size={30} />
            <div className="step-main">
              <span className="step-title">{cap(s.title)}</span>
              <span className="tiny faint">
                {s.collaborators.length > 0 ? `${s.owner_name}, with ${s.collaborators.map((c) => c.name).join(", ")}` : s.owner_name}
                {s.uncertain && " · depends on someone saying yes"}
                {s.note && ` · ${s.note}`}
              </span>
            </div>
            <span className="step-mins num">{minutes(s.minutes)}</span>
            {s.kind === "PRACTICE" ? (
              <Link to={`/h/${h.id}/practise?r=${s.responsibility}&p=${s.owner}`} className="btn btn-ghost btn-sm">
                <AudioLines size={14} aria-hidden="true" /> Practise
              </Link>
            ) : (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => onStep(s)}>
                <CircleDashed size={14} aria-hidden="true" /> Mark done
              </button>
            )}
          </li>
        ))}
      </ol>
    </article>
  );
}

function EvidenceDialog({ step, onClose }: { step: Step | null; onClose: () => void }) {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const [kind, setKind] = useState("AGREEMENT");
  const [witness, setWitness] = useState("");
  const [note, setNote] = useState("");
  const [date, setDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!step) return;
    setKind(EVIDENCE_KINDS.some((k) => k.id === step.evidence) ? step.evidence : "APP");
    setWitness(h.people.find((p) => !p.minor && p.id !== step.owner)?.id ?? "");
    setNote("");
    setDate("");
    setFile(null);
  }, [step, h.people]);
  const needsWitness = step?.kind === "DEMONSTRATE";
  const needsDate = step?.kind === "RENEW_EARLY";
  const submit = async () => {
    if (!step) return;
    const form = new FormData();
    form.set("step_id", step.id);
    form.set("kind", needsWitness ? "WITNESS" : kind);
    if (needsWitness) form.set("witness", witness);
    if (note) form.set("note", note);
    if (needsDate && date) form.set("new_date", date);
    if (file) form.set("file", file);
    setBusy(true);
    try {
      const out = await api.evidence(h.id, form);
      setHousehold(out.household);
      toast(out.recorded.changes[0] ?? "Recorded. The result has been updated.");
      onClose();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={!!step}
      onClose={onClose}
      title="How do you know it's done?"
      footer={
        <>
          <button type="button" className="btn btn-quiet" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" disabled={busy || (needsWitness && !witness)} onClick={() => void submit()}>
            Record it
          </button>
        </>
      }
    >
      {step && (
        <div className="stack">
          <p className="lead-text">{cap(step.title)}</p>
          {needsWitness ? (
            <Field label="Who watched?">
              <select className="input" value={witness} onChange={(e) => setWitness(e.target.value)}>
                {h.people
                  .filter((p) => !p.minor && p.id !== step.owner)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </Field>
          ) : (
            <Field label="Evidence">
              <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
                {EVIDENCE_KINDS.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.label}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {needsDate && (
            <Field label="New expiry date">
              <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
          )}
          <Field label="Note (optional)">
            <input className="input" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <Field label="Attach a photo (optional)">
            <input className="input" type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Field>
          <p className="tiny faint">This records what your household says happened. It doesn't contact anyone or change anything outside this app.</p>
        </div>
      )}
    </Modal>
  );
}
