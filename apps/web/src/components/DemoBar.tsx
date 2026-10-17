import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FastForward, FlaskConical, RotateCcw, Rewind, Shuffle } from "lucide-react";
import { api, errorText } from "../lib/api";
import type { DemoSummary } from "../lib/types";
import { useLoaded, useToast } from "../state/app";

/** Controls for the sample households: jump a week ahead, try a "what if", switch household. */
export function DemoBar() {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [demos, setDemos] = useState<DemoSummary[]>([]);
  const later = h.stages_applied.length > 0;
  const canJump = h.stages_available.includes("after_handover");

  useEffect(() => {
    api.demos().then(setDemos, () => undefined);
  }, []);

  const run = async (fn: () => Promise<typeof h>, done: string) => {
    setBusy(true);
    try {
      setHousehold(await fn());
      toast(done);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="demo-bar glass" data-tour="demo-bar" role="region" aria-label="Sample household controls">
      <span className="demo-label">
        <FlaskConical size={15} aria-hidden="true" /> Sample household
      </span>
      {demos.length > 1 && (
        <label className="demo-select">
          <span className="sr-only">Open another sample household</span>
          <select
            value={h.demo_source ?? ""}
            disabled={busy}
            onChange={(e) => navigate(`/demo/${e.target.value}`)}
          >
            {demos.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {canJump && (
        <button
          type="button"
          className={`btn btn-sm ${later ? "btn-ghost" : "btn-primary"}`}
          disabled={busy}
          onClick={() =>
            void run(
              () => api.demoStage(h.id, later ? "capture" : "after_handover"),
              later ? "Back to the start." : "A week later: the family recorded agreements, photos and practice.",
            )
          }
        >
          {later ? <Rewind size={15} aria-hidden="true" /> : <FastForward size={15} aria-hidden="true" />}
          {later ? "Back to the start" : "Jump a week ahead"}
        </button>
      )}
      {h.variants.length > 0 && (
        <label className="demo-select">
          <Shuffle size={15} aria-hidden="true" />
          <span className="sr-only">What if</span>
          <select
            value={h.variant ?? ""}
            disabled={busy}
            onChange={(e) => {
              const v = e.target.value || null;
              const title = h.variants.find((x) => x.id === v)?.title;
              void run(() => api.demoVariant(h.id, v), v ? `What if: ${title}` : "Back to what was recorded.");
            }}
          >
            <option value="">What if… (as recorded)</option>
            {h.variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={() => void run(() => api.startDemo(true, h.demo_source ?? undefined), "The sample household is back to the start.")}>
        <RotateCcw size={15} aria-hidden="true" /> Reset
      </button>
    </div>
  );
}
