import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { Bot, Check, ChevronDown, Radar, X } from "lucide-react";
import { QuoteSlips } from "../components/claims";
import { EmptyState, PageHeader, Segmented, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { fmtDay } from "../lib/format";
import { findingMeta, STATE } from "../lib/meta";
import type { Finding, HouseholdView } from "../lib/types";
import { useLoaded, useToast } from "../state/app";

const VERDICT: Record<string, string> = { uphold: "Upheld", narrow: "Narrowed", question: "Has a question" };

export default function Findings() {
  const { h, setHousehold } = useLoaded();
  const findings = h.analysis?.findings ?? [];
  const kinds = useMemo(() => [...new Set(findings.map((f) => f.kind))], [findings]);
  const [kind, setKind] = useState<string>("all");
  const location = useLocation();
  const shown = findings.filter((f) => kind === "all" || f.kind === kind);

  useEffect(() => {
    if (!location.hash) return;
    const el = document.getElementById(`f-${decodeURIComponent(location.hash.slice(1))}`);
    if (el) window.setTimeout(() => el.scrollIntoView({ block: "start", behavior: "smooth" }), 120);
  }, [location.hash]);

  return (
    <>
      <PageHeader
        title="What we found"
        lede="Ranked by how soon and how badly each one bites. Every finding shows how it was worked out, what was checked and set aside, and what a second AI reader thought of it."
      />
      {findings.length > 0 && kinds.length > 1 && (
        <div className="filter-row">
          <Segmented
            label="Show"
            size="sm"
            value={kind}
            onChange={setKind}
            options={[{ value: "all", label: `All (${findings.length})` }, ...kinds.map((k) => ({ value: k, label: findingMeta(k).label }))]}
          />
        </div>
      )}
      {findings.length === 0 ? (
        <EmptyState icon={<Radar size={28} />} title="Nothing to show yet">
          Either everything works, or nothing has been recorded yet. Add a voice note or a photo to get started.
        </EmptyState>
      ) : (
        <div className="findings">
          {shown.map((f, i) => (
            <FindingCard key={f.id} f={f} h={h} onChanged={setHousehold} tour={i === 0 ? "finding" : undefined} />
          ))}
        </div>
      )}
    </>
  );
}

export function FindingCard({ f, h, onChanged, tour }: { f: Finding; h: HouseholdView; onChanged: (h: HouseholdView) => void; tour?: string }) {
  const meta = findingMeta(f.kind);
  const Icon = meta.icon;
  const [open, setOpen] = useState(false);
  const claims = h.claims.filter((c) => f.claim_ids.includes(c.id));
  const kept = f.considered.filter((c) => c.verdict === "retained");
  const aside = f.considered.filter((c) => c.verdict === "set_aside");
  const states = new Map((h.analysis?.result.responsibilities ?? []).map((r) => [r.id, r.state]));
  const worst = f.responsibilities.map((r) => states.get(r.id) ?? "blocked").sort((a, b) => STATE[a].order - STATE[b].order)[0] ?? "blocked";
  const held = f.kind === "HELD_BY_LEAVER";
  const leaver = h.people.find((p) => p.id === h.settings.leaver)?.name ?? "the person leaving";

  return (
    <article className="finding" id={`f-${f.id}`} data-tour={tour} style={{ ["--f-tone" as string]: STATE[worst].fill }} aria-labelledby={`ft-${f.id}`}>
      <div className="finding-head">
        <span className="finding-kind">
          <Icon size={16} aria-hidden="true" /> {meta.label}
        </span>
        <span className="finding-dates num">
          {f.dates.slice(0, 3).map((d) => (
            <span key={d}>{fmtDay(d)}</span>
          ))}
          {f.dates.length > 3 && <span>+{f.dates.length - 3}</span>}
        </span>
      </div>
      <h2 id={`ft-${f.id}`}>{f.title}</h2>
      <p className="finding-summary">{f.summary}</p>

      {held && (
        <div className="held">
          <div className="held-items">
            {f.path
              .filter((n) => n.kind === "resource")
              .map((n) => (
                <span key={n.id} className="held-item">
                  {n.label}
                </span>
              ))}
          </div>
          <p className="tiny faint">Only {leaver} can see these clearly. Hand them over and the glass clears.</p>
        </div>
      )}

      {f.responsibilities.length > 0 && (
        <div className="finding-affects">
          <span className="tiny faint">Affects</span>
          {f.responsibilities.map((r) => (
            <span key={r.id} className="affect">
              {r.label} <StateBadge state={states.get(r.id) ?? "blocked"} size="sm" />
            </span>
          ))}
        </div>
      )}

      {f.challenge && (
        <div className={`verdict v-${f.challenge.verdict}`}>
          <span className="verdict-head">
            <Bot size={15} aria-hidden="true" /> Second reader ({f.challenge.by === "gemini" ? "AI review" : f.challenge.by === "offline-rules" ? "offline rules" : f.challenge.by}):{" "}
            <strong>{VERDICT[f.challenge.verdict] ?? f.challenge.verdict}</strong>
          </span>
          <p>{f.challenge.explanation}</p>
        </div>
      )}

      <Answers f={f} h={h} onChanged={onChanged} />

      <button type="button" className="disclose" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <ChevronDown size={16} aria-hidden="true" /> How we got there, and the evidence ({claims.length})
      </button>
      {open && (
        <div className="finding-more">
          {f.path.length > 1 && (
            <ol className="path">
              {f.path.map((n, i) => (
                <li key={`${n.id}-${i}`} className={`path-node k-${n.kind}`}>
                  <span className="path-kind">{n.kind}</span>
                  <span>{n.label}</span>
                </li>
              ))}
            </ol>
          )}
          {f.considered.length > 0 && (
            <ul className="checked">
              {kept.map((c) => (
                <li key={c.responsibility} className="kept">
                  <Check size={14} aria-hidden="true" /> <strong>Kept:</strong> {c.message}
                </li>
              ))}
              {aside.map((c) => (
                <li key={c.responsibility} className="aside">
                  <X size={14} aria-hidden="true" /> <strong>Set aside:</strong> {c.message}
                </li>
              ))}
            </ul>
          )}
          <QuoteSlips claims={claims} h={h} />
        </div>
      )}
    </article>
  );
}

function Answers({ f, h, onChanged }: { f: Finding; h: HouseholdView; onChanged: (h: HouseholdView) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const send = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      const out = await api.answer(h.id, f.id, body);
      onChanged(out.household);
      toast(out.changes[0] ?? "Saved. The result has been updated.");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };
  if (f.kind === "CONTRADICTION") {
    const claims = h.claims.filter((c) => f.claim_ids.includes(c.id));
    return (
      <div className="answer">
        <span className="answer-q">Which is right?</span>
        <div className="row">
          {claims.map((c) => (
            <button key={c.id} type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void send({ keep_claim: c.id })}>
              {c.value}
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (f.kind === "NOT_ASKED") {
    return (
      <div className="answer">
        {f.asks.map((a) => (
          <div key={`${a.person}-${a.responsibility}`} className="answer-line">
            <span className="answer-q">{a.question}</span>
            <div className="row">
              {(["yes", "no", "unsure"] as const).map((v) => (
                <button key={v} type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void send({ person: a.person, responsibility: a.responsibility, value: v })}>
                  {v === "yes" ? "Yes" : v === "no" ? "No" : "Not sure"}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }
  if (f.challenge?.verdict === "question" && f.challenge.question) {
    return (
      <div className="answer">
        <span className="answer-q">{f.challenge.question}</span>
        <div className="row">
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void send({ confirm: true })}>
            Yes, that's right
          </button>
          <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={() => void send({ confirm: false })}>
            No, that's wrong
          </button>
        </div>
      </div>
    );
  }
  return null;
}
