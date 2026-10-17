import { useEffect, useRef, useState } from "react";
import { Cpu, Infinity as InfinityIcon, Sparkles } from "lucide-react";
import { useUsage } from "../state/app";
import { fmtTime } from "../lib/format";
import type { AiUsage, UsageRow } from "../lib/types";
import { Meter } from "./ui";

const ROLE_NAMES: Record<string, string> = {
  listener: "Voice notes",
  reader: "Photos and PDFs",
  extractor: "Finding facts",
  challenger: "AI review",
  grader: "Checking practice",
};

function totals(u: AiUsage): { used: number; usable: number } {
  let used = 0;
  let usable = 0;
  for (const m of u.models) {
    if (m.usable_today != null) {
      used += m.used_today;
      usable += m.usable_today;
    }
  }
  return { used, usable };
}

function tone(row: UsageRow): "ok" | "warn" | "bad" {
  if (row.usable_today == null) return "ok";
  const left = row.left_today ?? 0;
  if (left === 0 || row.note === "used up for today") return "bad";
  if (left / row.usable_today < 0.2) return "warn";
  return "ok";
}

export function AiRows({ usage }: { usage: AiUsage }) {
  return (
    <ul className="ai-rows">
      {usage.models.map((m) => (
        <li key={m.model}>
          <div className="ai-row-head">
            <span className="ai-model">
              <Cpu size={14} aria-hidden="true" />
              {m.label}
            </span>
            <span className="num small">
              {m.limit_today == null ? "no daily limit" : `${m.used_today} of ${m.usable_today} today`}
            </span>
          </div>
          {m.usable_today != null && <Meter value={m.used_today} max={m.usable_today} tone={tone(m)} label={`${m.label}: ${m.used_today} of ${m.usable_today} used today`} />}
          <div className="ai-row-foot tiny faint">
            {m.limit_per_minute != null && (
              <span className="num">
                {m.used_this_minute}/{m.limit_per_minute} this minute
              </span>
            )}
            {m.note && <span className="ai-note">{m.note}</span>}
            {m.cooling_down_for > 0 && <span className="num">ready again in {m.cooling_down_for} s</span>}
          </div>
        </li>
      ))}
      <li className="ai-live-row">
        <div className="ai-row-head">
          <span className="ai-model">
            <Cpu size={14} aria-hidden="true" />
            {usage.live_model.label}
          </span>
          <span className="small">
            <InfinityIcon size={14} aria-hidden="true" style={{ display: "inline", verticalAlign: "-2px" }} /> spoken practice, no daily limit
          </span>
        </div>
      </li>
    </ul>
  );
}

export function AiChains({ usage }: { usage: AiUsage }) {
  return (
    <dl className="ai-chains">
      {Object.entries(usage.chains).map(([role, chain]) => (
        <div key={role}>
          <dt>{ROLE_NAMES[role] ?? role}</dt>
          <dd>
            {chain.map((c, i) => (
              <span key={c.model}>
                {i > 0 && <span className="faint"> → </span>}
                {c.label}
                {c.keep > 0 && <span className="faint"> (keeps {c.keep})</span>}
              </span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The live allowance meter: a pill in the top bar that opens the details. */
export function AiPill() {
  const { usage, updatedAt } = useUsage();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (!updatedAt) return;
    setFlash(true);
    const t = window.setTimeout(() => setFlash(false), 900);
    return () => window.clearTimeout(t);
  }, [updatedAt]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!usage) return null;
  const offline = usage.mode !== "live";
  const t = totals(usage);
  return (
    <div className="ai-pill-wrap" ref={box} data-tour="ai-allowance">
      <button type="button" className={`ai-pill ${offline ? "offline" : ""}`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className={`live-dot ${flash ? "flash" : ""}`} aria-hidden="true" />
        <Sparkles size={15} aria-hidden="true" />
        <span className="ai-pill-text">
          {offline ? "Offline demo" : usage.tier === "free" ? "Free AI" : "Gemini"}
          {!offline && t.usable > 0 && <span className="num ai-pill-count"> · {Math.max(0, t.usable - t.used)} left today</span>}
        </span>
      </button>
      {open && (
        <div className="ai-pop glass-pop" role="dialog" aria-label="AI allowance today">
          <AiAllowanceBody usage={usage} />
        </div>
      )}
    </div>
  );
}

export function AiAllowanceBody({ usage }: { usage: AiUsage }) {
  const offline = usage.mode !== "live";
  return (
    <div className="ai-body">
      <div className="ai-body-head">
        <strong>{offline ? "Offline demo" : usage.tier === "free" ? "Runs on the free Gemini tier" : "Gemini (paid tier)"}</strong>
        <span className="tiny faint">
          <span className="live-dot small" aria-hidden="true" /> Live · resets at {fmtTime(usage.resets_at)}
        </span>
      </div>
      {offline ? (
        <p className="small muted">
          No Gemini key is set, so AI steps replay the reviewed sample data and say so. Everything else (the engine, the plan, the card) works the same.
        </p>
      ) : (
        <>
          <AiRows usage={usage} />
          {usage.visitor.limit_today != null && (
            <p className="small">
              You have used <strong className="num">{usage.visitor.used_today}</strong> of your <span className="num">{usage.visitor.limit_today}</span> AI calls today.
            </p>
          )}
          {usage.reused_answers > 0 && <p className="tiny faint">{usage.reused_answers} answers reused for identical requests (no allowance used).</p>}
        </>
      )}
      <details className="more">
        <summary>Which model does what</summary>
        <AiChains usage={usage} />
        <p className="tiny faint">Best model first; when one is busy or used up, the next one answers. Every answer is checked against its schema before it's used.</p>
      </details>
    </div>
  );
}
