import { Fragment } from "react";
import { BrainCircuit, ChevronRight, Code2, Cpu, RefreshCw } from "lucide-react";
import { JobProgress, PageHeader, Panel } from "../components/ui";
import { fmtAgo } from "../lib/format";
import { STEP_NAMES } from "../lib/meta";
import type { TraceStep } from "../lib/types";
import { useAnalyze } from "../state/analyze";
import { useLoaded } from "../state/app";

/** The stages of a full check, in order. "ai" stages are answered by a Google model;
 *  "code" stages are deterministic and decide every number. */
const FLOW: { node: string; who: "ai" | "code"; what: string }[] = [
  { node: "compile_claims", who: "code", what: "Accepted facts become one model of the household." },
  { node: "evaluate_scenario", who: "code", what: "Every date of the absence is simulated: who can do it, with what." },
  { node: "discover_findings", who: "code", what: "Hidden problems are found: things held by the person leaving, clashes, deadlines." },
  { node: "challenger", who: "ai", what: "A second AI reader upholds, narrows or questions each finding, citing facts." },
  { node: "apply_challenge", who: "code", what: "Only checks that cite real facts are applied. The AI can't change a number." },
  { node: "plan_preparation", who: "code", what: "The fewest steps that fix the most, for the time you have." },
];

const READING: { node: string; who: "ai" | "code"; what: string }[] = [
  { node: "listener", who: "ai", what: "Voice notes are written down." },
  { node: "reader", who: "ai", what: "Photos and PDFs are read." },
  { node: "extractor", who: "ai", what: "Facts are pulled out, each with its exact words." },
  { node: "verify_and_resolve", who: "code", what: "Every quote is checked against the source. No match, no fact." },
];

function Stage({ node, who, what, step }: { node: string; who: "ai" | "code"; what: string; step?: TraceStep }) {
  return (
    <li className={`flow-stage ${who}`}>
      <span className="flow-kind">
        {who === "ai" ? <BrainCircuit size={14} aria-hidden="true" /> : <Code2 size={14} aria-hidden="true" />}
        {who === "ai" ? "AI reads" : "Code decides"}
      </span>
      <strong>{STEP_NAMES[node] ?? node}</strong>
      <span className="small muted">{what}</span>
      {step && (
        <span className="flow-meta tiny">
          {step.model_label && (
            <span className="model-chip">
              <Cpu size={11} aria-hidden="true" /> {step.model_label}
            </span>
          )}
          {step.summary && <span className="faint">{step.summary.replaceAll("_", " ")}</span>}
        </span>
      )}
    </li>
  );
}

export default function Trace() {
  const { h } = useLoaded();
  const a = h.analysis;
  const { run, running, steps } = useAnalyze();
  const accepted = h.claims.filter((c) => c.review === "accepted").length;
  const lastFull = a ? (a.workflow === "engine-refresh" ? (a.review_trace ?? []) : a.trace) : [];
  const shown = running || steps.length ? steps : lastFull;
  const byNode = new Map(shown.map((s) => [s.node, s]));
  const aiMs = shown.filter((s) => s.kind === "agent").reduce((n, s) => n + s.ms, 0);
  const codeMs = shown.filter((s) => s.kind === "code").reduce((n, s) => n + s.ms, 0);
  const total = Math.max(1, aiMs + codeMs);
  const models = [...new Set(shown.map((s) => s.model_label).filter(Boolean))] as string[];
  const reviewedAt = a?.workflow === "engine-refresh" ? a.review_at : a?.computed_at;

  return (
    <>
      <PageHeader
        title="How it was worked out"
        lede="Every step of the last check, and which Google model answered each AI step. The AI reads and reviews; code decides what stops, so the same facts always give the same answer."
        actions={
          <button type="button" className="btn btn-primary" disabled={running} onClick={() => void run()}>
            <RefreshCw size={16} aria-hidden="true" className={running ? "spin" : undefined} /> {running ? "Checking…" : "Check again with AI"}
          </button>
        }
      />

      <Panel title="A full check, step by step" eyebrow="Each step is marked: AI reads, or code decides" tone="glass" className="flow-panel">
        <ol className="flow">
          {FLOW.map((f, i) => (
            <Fragment key={f.node}>
              {i > 0 && (
                <li className="flow-arrow" aria-hidden="true">
                  <ChevronRight size={16} />
                </li>
              )}
              <Stage {...f} step={byNode.get(f.node)} />
            </Fragment>
          ))}
        </ol>
        <details className="more">
          <summary>And before that: reading what the family added</summary>
          <ol className="flow small-flow">
            {READING.map((f, i) => (
              <Fragment key={f.node}>
                {i > 0 && (
                  <li className="flow-arrow" aria-hidden="true">
                    <ChevronRight size={16} />
                  </li>
                )}
                <Stage {...f} />
              </Fragment>
            ))}
          </ol>
        </details>
      </Panel>

      <div className="trace-grid">
        <Panel title={running ? "Checking now…" : "The last check"} eyebrow={reviewedAt ? `AI review ${fmtAgo(reviewedAt)}` : "No AI review yet"} className="span-7">
          {shown.length ? (
            <JobProgress steps={shown} running={running} />
          ) : (
            <p className="small muted">Nothing has been checked with AI yet. Press "Check again with AI" to run the full check and watch each step.</p>
          )}
          {a?.workflow === "engine-refresh" && lastFull.length > 0 && !running && !steps.length && (
            <p className="tiny faint">Since then, the engine has updated the results after each change (no AI needed). Check again for a fresh AI review.</p>
          )}
        </Panel>

        <Panel title="This check in numbers" className="span-5">
          {shown.length > 0 && (
            <div className="time-split">
              <div className="time-bar" role="img" aria-label={`AI ${(aiMs / 1000).toFixed(1)} seconds, code ${(codeMs / 1000).toFixed(1)} seconds`}>
                <span className="ai" style={{ width: `${(100 * aiMs) / total}%` }} />
                <span className="code" style={{ width: `${(100 * codeMs) / total}%` }} />
              </div>
              <div className="row-between tiny">
                <span>
                  <i className="swatch ai" /> Gemini <span className="num">{(aiMs / 1000).toFixed(1)} s</span>
                </span>
                <span>
                  <i className="swatch code" /> Code <span className="num">{(codeMs / 1000).toFixed(1)} s</span>
                </span>
              </div>
            </div>
          )}
          <dl className="facts-table">
            <div>
              <dt>AI</dt>
              <dd>{h.ai.mode === "live" ? (h.ai.tier === "free" ? "Gemini, free tier" : "Gemini") : "Offline (replays reviewed sample answers)"}</dd>
            </div>
            <div>
              <dt>Models in this check</dt>
              <dd>
                {models.length ? (
                  <span className="chip-row">
                    {models.map((m) => (
                      <span key={m} className="model-chip">
                        <Cpu size={11} aria-hidden="true" /> {m}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="faint">None recorded</span>
                )}
              </dd>
            </div>
            <div>
              <dt>AI review</dt>
              <dd>{a?.challenge === "offline-rules" ? "Rules only (offline)" : a?.challenge === "gemini" ? "Gemini" : !a?.challenge || a.challenge === "none" ? "Not run yet" : a.challenge}</dd>
            </div>
            <div>
              <dt>Engine</dt>
              <dd className="num">
                {a?.result.engine_version ?? "—"} · rules {a?.result.policy_version ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Facts used</dt>
              <dd className="num">
                {accepted} accepted, from {h.sources.length} sources
              </dd>
            </div>
            <div>
              <dt>Household version</dt>
              <dd className="num">{a?.world_version ?? "—"}</dd>
            </div>
          </dl>
          {a && a.diagnostics.length > 0 && (
            <details className="more">
              <summary>Notes from the engine ({a.diagnostics.length})</summary>
              <ul className="diag">
                {a.diagnostics.map((d) => (
                  <li key={d} className="tiny muted">
                    {d}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </Panel>
      </div>
    </>
  );
}
