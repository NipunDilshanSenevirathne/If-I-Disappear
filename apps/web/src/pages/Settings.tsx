import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Compass, Download, Plus, RotateCcw, Save, Trash2, UserPlus } from "lucide-react";
import { AddResponsibility } from "../components/AddResponsibility";
import { AiAllowanceBody } from "../components/AiAllowance";
import { CategoryIcon } from "../components/household";
import { ThemeToggle } from "../components/shell/ThemeToggle";
import { householdTour, useTour } from "../components/tour/Tour";
import { Avatar, Field, Modal, PageHeader, Panel, Segmented, Spinner, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { addDays, cap, fmtDay, plural } from "../lib/format";
import { useLoaded, useToast, useUsage } from "../state/app";

const ROLE: Record<string, string> = {
  backup: "Takes over while away",
  household: "Lives at home",
  helper: "Helps from outside",
};

export default function Settings() {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const tour = useTour();
  const { usage } = useUsage();
  const navigate = useNavigate();
  const base = `/h/${h.id}`;
  const s = h.settings;
  const leaver = h.people.find((p) => p.id === s.leaver);

  // the absence
  const [form, setForm] = useState({ name: s.name, departure: s.departure, horizon_days: s.horizon_days, destination: s.destination ?? "", absence: s.absence ?? "travel" });
  const dirty =
    form.name !== s.name ||
    form.departure !== s.departure ||
    form.horizon_days !== s.horizon_days ||
    form.destination !== (s.destination ?? "") ||
    form.absence !== (s.absence ?? "travel");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      setHousehold(await api.patchSettings(h.id, { ...form, name: form.name.trim() || s.name }));
      toast("Saved. Everything has been worked out again for the new dates.");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setSaving(false);
    }
  };

  // people
  const [person, setPerson] = useState({ name: "", role: "household", minor: false });
  const addPerson = async () => {
    try {
      setHousehold(await api.addPerson(h.id, { ...person, name: person.name.trim() }));
      toast(`Added ${person.name.trim()}.`);
      setPerson({ name: "", role: "household", minor: false });
    } catch (e) {
      toast(errorText(e), "error");
    }
  };

  // responsibilities in this plan
  const responsibilities = useMemo(() => h.entities.filter((e) => e.kind === "responsibility"), [h.entities]);
  const results = new Map((h.analysis?.result.responsibilities ?? []).map((r) => [r.id, r]));
  const included = (id: string) => s.in_scope === null || s.in_scope.includes(id);
  const [scopeBusy, setScopeBusy] = useState<string | null>(null);
  const toggle = async (id: string, include: boolean) => {
    setScopeBusy(id);
    try {
      setHousehold(await api.setScope(h.id, id, include));
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setScopeBusy(null);
    }
  };
  const [adding, setAdding] = useState(false);

  // your data
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const exportJson = async () => {
    try {
      const data = await api.exportHousehold(h.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `if-i-disappear-${h.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) {
      toast(errorText(e), "error");
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteHousehold(h.id);
      toast("The household and everything in it has been deleted.");
      navigate("/");
    } catch (e) {
      toast(errorText(e), "error");
      setBusy(false);
    }
  };
  const resetSample = async () => {
    setBusy(true);
    try {
      const fresh = await api.startDemo(true, h.demo_source ?? undefined);
      navigate(`/h/${fresh.id}`);
      toast("The sample household is back to how it started.");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Household" lede="Who is leaving, when, and who is at home. Any change here is worked out again straight away." />
      <div className="settings-grid">
        <Panel title="The absence" className="span-7">
          <div className="stack">
            <div className="grid-2">
              <Field label="Household name">
                <input className="input" value={form.name} maxLength={80} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              <Field label="Who is leaving?" hint="Start a new household to change this.">
                <input className="input" value={leaver?.name ?? ""} readOnly aria-readonly="true" />
              </Field>
            </div>
            <Field label="What kind of absence?">
              <Segmented
                label="What kind of absence"
                value={form.absence}
                onChange={(v) => setForm({ ...form, absence: v })}
                options={[
                  { value: "travel", label: "Work abroad or travel" },
                  { value: "hospital", label: "A hospital stay" },
                  { value: "other", label: "Something else" },
                ]}
              />
            </Field>
            <div className="grid-3">
              <Field label="Leaves on">
                <input className="input" type="date" value={form.departure} onChange={(e) => e.target.value && setForm({ ...form, departure: e.target.value })} />
              </Field>
              <Field label="Days away" hint={`Back on ${fmtDay(addDays(form.departure, form.horizon_days - 1))}`}>
                <input
                  className="input num"
                  type="number"
                  min={7}
                  max={365}
                  value={form.horizon_days}
                  onChange={(e) => setForm({ ...form, horizon_days: Math.max(7, Math.min(365, Number(e.target.value) || 7)) })}
                />
              </Field>
              <Field label={form.absence === "hospital" ? "Which hospital? (optional)" : "Going to (optional)"}>
                <input className="input" value={form.destination} maxLength={60} onChange={(e) => setForm({ ...form, destination: e.target.value })} />
              </Field>
            </div>
            <input
              className="range"
              type="range"
              min={7}
              max={365}
              value={form.horizon_days}
              aria-label="Days away"
              onChange={(e) => setForm({ ...form, horizon_days: Number(e.target.value) })}
            />
            <div className="row">
              <button type="button" className="btn btn-primary" disabled={!dirty || saving} onClick={() => void save()}>
                {saving ? <Spinner size={15} /> : <Save size={16} aria-hidden="true" />} Save changes
              </button>
              {dirty && (
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => setForm({ name: s.name, departure: s.departure, horizon_days: s.horizon_days, destination: s.destination ?? "", absence: s.absence ?? "travel" })}
                >
                  Undo
                </button>
              )}
            </div>
          </div>
        </Panel>

        <Panel title="People" eyebrow={plural(h.people.length, "person", "people")} className="span-5">
          <ul className="people-list">
            {h.people.map((p) => (
              <li key={p.id}>
                <Avatar id={p.id} name={p.name} size={36} />
                <div className="grow">
                  <strong>{p.name}</strong>
                  <span className="tiny faint">
                    {p.id === s.leaver ? "Leaving" : (ROLE[p.role ?? ""] ?? "At home")}
                    {p.minor ? " · child" : ""}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          <form
            className="add-person"
            onSubmit={(e) => {
              e.preventDefault();
              if (person.name.trim()) void addPerson();
            }}
          >
            <Field label="Add someone">
              <input className="input" value={person.name} maxLength={60} placeholder="Their name" onChange={(e) => setPerson({ ...person, name: e.target.value })} />
            </Field>
            <div className="row">
              <select className="input" aria-label="Their part" value={person.role} onChange={(e) => setPerson({ ...person, role: e.target.value })}>
                <option value="backup">Takes over while away</option>
                <option value="household">Lives at home</option>
                <option value="helper">Helps from outside</option>
              </select>
              <label className="check small">
                <input type="checkbox" checked={person.minor} onChange={(e) => setPerson({ ...person, minor: e.target.checked })} /> A child
              </label>
              <button type="submit" className="btn btn-ghost" disabled={!person.name.trim()}>
                <UserPlus size={16} aria-hidden="true" /> Add
              </button>
            </div>
          </form>
        </Panel>

        <Panel
          title="What's in the plan"
          eyebrow={`${responsibilities.filter((r) => included(r.id)).length} of ${responsibilities.length} included`}
          className="span-7"
          actions={
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>
              <Plus size={15} aria-hidden="true" /> Add one by hand
            </button>
          }
        >
          <p className="small muted">Switch one off to leave it out of this absence (for example, it stops anyway). The counts say how many are included, so nothing is hidden.</p>
          <ul className="scope-list">
            {responsibilities.map((r) => {
              const on = included(r.id);
              const res = results.get(r.id);
              return (
                <li key={r.id} className={on ? "" : "off"}>
                  <CategoryIcon category={r.category ?? "household"} />
                  <span className="grow scope-name">{cap(r.name)}</span>
                  {on && res && <StateBadge state={res.state} size="sm" />}
                  {!on && <span className="tag">Left out</span>}
                  <button
                    type="button"
                    role="switch"
                    aria-checked={on}
                    aria-label={`Include ${r.name}`}
                    className="switch"
                    disabled={scopeBusy !== null}
                    onClick={() => void toggle(r.id, !on)}
                  >
                    <span />
                  </button>
                </li>
              );
            })}
            {responsibilities.length === 0 && <li className="small muted">Nothing yet. Add a voice note, a photo or one by hand.</li>}
          </ul>
        </Panel>

        <Panel title="AI allowance today" className="span-5" tone="glass">
          {usage ? <AiAllowanceBody usage={usage} /> : <Spinner label="Loading…" />}
        </Panel>

        <Panel title="Appearance and help" className="span-5">
          <div className="stack">
            <Field label="Colours">
              <ThemeToggle withLabels />
            </Field>
            <p className="tiny faint">Saved on this device only.</p>
            <button type="button" className="btn btn-ghost" onClick={() => tour.start(householdTour(leaver?.name ?? "The person leaving", h.demo), base)}>
              <Compass size={16} aria-hidden="true" /> Take the tour again
            </button>
          </div>
        </Panel>

        <Panel title="Your data" className="span-7">
          <div className="stack">
            <p className="small muted">
              Everything about this household is kept in one place and can be taken away or deleted. The card and the links never contain passwords, PINs or account numbers.
            </p>
            <div className="row">
              <button type="button" className="btn btn-ghost" onClick={() => void exportJson()}>
                <Download size={16} aria-hidden="true" /> Download everything (JSON)
              </button>
              {h.demo && (
                <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void resetSample()}>
                  <RotateCcw size={16} aria-hidden="true" /> Start the sample again
                </button>
              )}
            </div>
            {!confirmDelete ? (
              <button type="button" className="btn btn-quiet danger align-start" onClick={() => setConfirmDelete(true)}>
                <Trash2 size={16} aria-hidden="true" /> Delete this household
              </button>
            ) : (
              <div className="danger-zone" role="alert">
                <strong>Delete {h.name} for good?</strong>
                <span className="small muted">Sources, facts, the plan, practice and every link you made will be deleted. This can't be undone.</span>
                <div className="row">
                  <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void remove()}>
                    <Trash2 size={16} aria-hidden="true" /> Delete it
                  </button>
                  <button type="button" className="btn btn-quiet" onClick={() => setConfirmDelete(false)}>
                    Keep it
                  </button>
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <Modal open={adding} onClose={() => setAdding(false)} title="Add a responsibility by hand" wide>
        <AddResponsibility
          h={h}
          onAdded={(next) => {
            setHousehold(next);
            setAdding(false);
          }}
        />
      </Modal>
    </>
  );
}
