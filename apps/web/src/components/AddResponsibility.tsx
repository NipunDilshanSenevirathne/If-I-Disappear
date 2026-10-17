import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, errorText } from "../lib/api";
import type { HouseholdView, NewResponsibility } from "../lib/types";
import { useToast } from "../state/app";
import { Field, Segmented } from "./ui";

const DAYS = [
  ["MO", "Mon"],
  ["TU", "Tue"],
  ["WE", "Wed"],
  ["TH", "Thu"],
  ["FR", "Fri"],
  ["SA", "Sat"],
  ["SU", "Sun"],
] as const;

const CATEGORIES = [
  ["bills", "Bills"],
  ["money", "Money"],
  ["health", "Health and care"],
  ["school", "School and children"],
  ["home", "Home"],
  ["vehicle", "Vehicle"],
  ["documents", "Documents"],
  ["work", "Work and income"],
] as const;

const KINDS = [
  ["document", "A paper or document"],
  ["contact", "A phone contact"],
  ["account", "An app or account"],
  ["item", "A thing (a key, a card…)"],
  ["phone_number", "A phone number"],
  ["location", "A place"],
] as const;

/** Add a responsibility from a short form. No AI: the facts are saved as reviewed,
 *  each quoting a sentence of a "typed in" note, so they work like any others. */
export function AddResponsibility({ h, onAdded }: { h: HouseholdView; onAdded: (h: HouseholdView) => void }) {
  const toast = useToast();
  const leaver = h.settings.leaver;
  const adults = h.people.filter((p) => !p.minor);
  const takers = adults.filter((p) => p.id !== leaver);
  const [f, setF] = useState<NewResponsibility>({
    label: "",
    category: "bills",
    freq: "monthly",
    interval: 1,
    weekdays: [],
    monthday: 10,
    date: null,
    window_start: null,
    window_end: null,
    usual: leaver,
    taker: takers.find((p) => p.role === "backup")?.id ?? takers[0]?.id ?? null,
    agreed: "unsure",
    importance: 2,
    needs: [],
    key_step: null,
  });
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<NewResponsibility>) => setF((x) => ({ ...x, ...patch }));
  const valid = f.label.trim().length >= 3 && (f.freq !== "weekly" || f.weekdays.length > 0) && (f.freq !== "once" || !!f.date);

  const submit = async () => {
    setBusy(true);
    try {
      const out = await api.addResponsibility(h.id, {
        ...f,
        needs: f.needs.filter((n) => n.name.trim()),
        key_step: f.key_step?.trim() || null,
        monthday: f.freq === "monthly" ? f.monthday : null,
        date: f.freq === "once" || f.freq === "weekly" ? f.date : null,
      });
      onAdded(out.household);
      toast(`Added "${f.label.trim()}". The result has been updated.`);
      set({ label: "", needs: [], key_step: null });
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="addresp">
      <div className="grid-2">
        <Field label="What has to be done?">
          <input className="input" value={f.label} maxLength={90} placeholder="Pay the water bill" onChange={(e) => set({ label: e.target.value })} />
        </Field>
        <Field label="What kind of thing is it?">
          <select className="input" value={f.category} onChange={(e) => set({ category: e.target.value })}>
            {CATEGORIES.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="How often?">
        <Segmented
          label="How often"
          size="sm"
          value={f.freq}
          onChange={(v) => set({ freq: v })}
          options={[
            { value: "once", label: "Once" },
            { value: "weekly", label: "Weekly" },
            { value: "monthly", label: "Monthly" },
            { value: "ongoing", label: "All the time" },
          ]}
        />
      </Field>
      {f.freq === "weekly" && (
        <div className="grid-2">
          <fieldset className="choice-group">
            <legend>On which day?</legend>
            <div className="chips">
              {DAYS.map(([v, l]) => (
                <button
                  key={v}
                  type="button"
                  className={`choice ${f.weekdays.includes(v) ? "on" : ""}`}
                  aria-pressed={f.weekdays.includes(v)}
                  onClick={() => set({ weekdays: f.weekdays.includes(v) ? f.weekdays.filter((d) => d !== v) : [...f.weekdays, v] })}
                >
                  {l}
                </button>
              ))}
            </div>
          </fieldset>
          <Field label="Every">
            <select className="input" value={f.interval} onChange={(e) => set({ interval: Number(e.target.value) })}>
              <option value={1}>week</option>
              <option value={2}>second week</option>
              <option value={3}>third week</option>
              <option value={4}>fourth week</option>
            </select>
          </Field>
        </div>
      )}
      {f.freq === "monthly" && (
        <Field label="On which day of the month?">
          <input className="input" type="number" min={1} max={31} value={f.monthday ?? 1} onChange={(e) => set({ monthday: Number(e.target.value) })} />
        </Field>
      )}
      {f.freq === "once" && (
        <Field label="On which date?">
          <input className="input" type="date" value={f.date ?? ""} onChange={(e) => set({ date: e.target.value || null })} />
        </Field>
      )}

      <div className="grid-2">
        <Field label="Who usually does it?">
          <select className="input" value={f.usual ?? leaver} onChange={(e) => set({ usual: e.target.value })}>
            {adults.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Who will do it while away?">
          <select className="input" value={f.taker ?? ""} onChange={(e) => set({ taker: e.target.value || null })}>
            <option value="">Nobody yet</option>
            {takers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {f.taker && (
        <Field label="Have they agreed?">
          <Segmented
            label="Have they agreed"
            size="sm"
            value={f.agreed}
            onChange={(v) => set({ agreed: v })}
            options={[
              { value: "yes", label: "Yes" },
              { value: "unsure", label: "Not asked yet" },
              { value: "no", label: "No" },
            ]}
          />
        </Field>
      )}
      <Field label="How much does it matter?">
        <Segmented
          label="How much does it matter"
          size="sm"
          value={f.importance}
          onChange={(v) => set({ importance: v })}
          options={[
            { value: 1, label: "A little" },
            { value: 2, label: "A lot" },
            { value: 3, label: "It must not be missed" },
          ]}
        />
      </Field>

      <fieldset className="choice-group">
        <legend>What does it need?</legend>
        <p className="tiny faint">Papers, contacts, apps or things. Never type a password or PIN; just say it exists.</p>
        {f.needs.map((n, i) => (
          <div key={i} className="need-row">
            <input
              className="input"
              value={n.name}
              placeholder="the water bill"
              aria-label={`Thing ${i + 1}`}
              onChange={(e) => set({ needs: f.needs.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })}
            />
            <select className="input" aria-label="What kind" value={n.kind} onChange={(e) => set({ needs: f.needs.map((x, j) => (j === i ? { ...x, kind: e.target.value } : x)) })}>
              {KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select
              className="input"
              aria-label="Who has it now"
              value={n.held_by ?? ""}
              onChange={(e) => set({ needs: f.needs.map((x, j) => (j === i ? { ...x, held_by: e.target.value || null } : x)) })}
            >
              <option value="">Anyone at home can get it</option>
              {adults.map((p) => (
                <option key={p.id} value={p.id}>
                  Only {p.name} has it
                </option>
              ))}
            </select>
            {f.taker && n.held_by && n.held_by !== f.taker && (
              <label className="check small">
                <input type="checkbox" checked={n.taker_has_it} onChange={(e) => set({ needs: f.needs.map((x, j) => (j === i ? { ...x, taker_has_it: e.target.checked } : x)) })} />
                {adults.find((p) => p.id === f.taker)?.name} has it too
              </label>
            )}
            <button type="button" className="icon-btn" aria-label={`Remove thing ${i + 1}`} onClick={() => set({ needs: f.needs.filter((_, j) => j !== i) })}>
              <Trash2 size={15} aria-hidden="true" />
            </button>
          </div>
        ))}
        {f.needs.length < 8 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => set({ needs: [...f.needs, { name: "", kind: "document", held_by: leaver, taker_has_it: false }] })}>
            <Plus size={15} aria-hidden="true" /> Add something it needs
          </button>
        )}
      </fieldset>
      <Field label="The one step that must not be missed (optional)">
        <input className="input" value={f.key_step ?? ""} maxLength={200} placeholder="Take the bill to the post office before the 10th" onChange={(e) => set({ key_step: e.target.value })} />
      </Field>
      <div className="row">
        <button type="button" className="btn btn-primary" disabled={busy || !valid} onClick={() => void submit()}>
          <Plus size={16} aria-hidden="true" /> Add it
        </button>
        <span className="tiny faint">Saved as facts you typed in. No AI is used.</span>
      </div>
    </div>
  );
}
