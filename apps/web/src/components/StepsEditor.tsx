import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, errorText } from "../lib/api";
import { cap } from "../lib/format";
import type { DraftStep, HouseholdView } from "../lib/types";
import { useToast } from "../state/app";
import { Field, Panel, Spinner } from "./ui";

/** Write or edit the approved steps for a task. The first draft is written by code
 *  from the household's own accepted facts; a person changes it and approves it. */
export function StepsEditor({ hid, responsibility, onSaved, onCancel }: { hid: string; responsibility: string; onSaved: (h: HouseholdView) => void; onCancel?: () => void }) {
  const toast = useToast();
  const [steps, setSteps] = useState<DraftStep[] | null>(null);
  const [prompt, setPrompt] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSteps(null);
    api.procedureDraft(hid, responsibility).then(
      (d) => {
        setSteps(d.steps.length ? d.steps : [{ text: "", critical: true, hint: null }]);
        setPrompt(d.scenario_prompt);
        setLabel(d.label);
      },
      (e) => toast(errorText(e), "error"),
    );
  }, [hid, responsibility, toast]);

  if (!steps) return <Spinner label="Drafting the steps…" />;
  const update = (i: number, patch: Partial<DraftStep>) => setSteps((xs) => (xs ?? []).map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const usable = steps.filter((s) => s.text.trim());

  const save = async () => {
    setBusy(true);
    try {
      const h = await api.saveProcedure(hid, responsibility, { steps: usable, scenario_prompt: prompt });
      toast("Steps approved. Practice is checked against these.");
      onSaved(h);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={`Steps for: ${cap(label)}`} eyebrow="Drafted from what your household already said">
      <p className="small muted">Change anything, mark the key steps, then approve. Explanations are checked against these steps.</p>
      <Field label="The situation to start from">
        <input className="input" value={prompt} maxLength={300} onChange={(e) => setPrompt(e.target.value)} />
      </Field>
      <ol className="edit-steps">
        {steps.map((s, i) => (
          <li key={i}>
            <Field label={`Step ${i + 1}`}>
              <textarea className="input textarea" rows={2} maxLength={300} value={s.text} onChange={(e) => update(i, { text: e.target.value })} />
            </Field>
            <div className="row-between">
              <label className="check">
                <input type="checkbox" checked={s.critical} onChange={(e) => update(i, { critical: e.target.checked })} />
                <span className="small">Key step</span>
              </label>
              <button
                type="button"
                className="icon-btn"
                aria-label={`Remove step ${i + 1}`}
                disabled={steps.length <= 1}
                onClick={() => setSteps((xs) => (xs ?? []).filter((_, j) => j !== i))}
              >
                <Trash2 size={15} aria-hidden="true" />
              </button>
            </div>
          </li>
        ))}
      </ol>
      <div className="row-between">
        <button type="button" className="btn btn-ghost btn-sm" disabled={steps.length >= 12} onClick={() => setSteps((xs) => [...(xs ?? []), { text: "", critical: false, hint: null }])}>
          <Plus size={15} aria-hidden="true" /> Add a step
        </button>
        <div className="row">
          {onCancel && (
            <button type="button" className="btn btn-quiet" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
          )}
          <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={busy || usable.length === 0}>
            Approve the steps
          </button>
        </div>
      </div>
    </Panel>
  );
}
