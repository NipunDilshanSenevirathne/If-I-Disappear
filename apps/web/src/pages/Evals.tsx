import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, CircleDashed, Info, X } from "lucide-react";
import { PublicNav } from "../components/shell/PublicNav";
import { Donut } from "../components/charts/Donut";
import { Spinner } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, fmtDay } from "../lib/format";
import type { DemoSummary } from "../lib/types";

interface Metric {
  name: string;
  value: number | string | null;
  target?: string | null;
  status: string;
  note?: string;
  num?: number;
  den?: number;
}
interface ReportSection {
  id?: string;
  title: string;
  summary?: string;
  metrics: Metric[];
  details?: string[];
}
interface Report {
  available: boolean;
  note?: string;
  generated?: string;
  commit?: string | null;
  ai_mode?: string;
  engine?: string;
  policy?: string;
  totals?: { pass: number; fail: number; not_run: number; info: number };
  sections?: ReportSection[];
}

const STATUS: Record<string, { label: string; color: string; soft: string; icon: typeof Check }> = {
  pass: { label: "Pass", color: "var(--st-prepared)", soft: "var(--st-prepared-soft)", icon: Check },
  fail: { label: "Fail", color: "var(--st-blocked)", soft: "var(--st-blocked-soft)", icon: X },
  "not run": { label: "Not run", color: "var(--st-confirm)", soft: "var(--st-confirm-soft)", icon: CircleDashed },
  info: { label: "For context", color: "var(--ink-2)", soft: "var(--surface-3)", icon: Info },
};

function StatusChip({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.info;
  return (
    <span className="status-chip" style={{ color: s.color, background: s.soft }}>
      <s.icon size={13} aria-hidden="true" strokeWidth={2.6} /> {s.label}
    </span>
  );
}

/** The harness writes tables, checklists and plain lines in Markdown; show them as such. */
function Details({ lines }: { lines: string[] }) {
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i]
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells);
        i++;
      }
      const [head, ...body] = rows;
      out.push(
        <div key={`t${i}`} className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                {head.map((c, j) => (
                  <th key={j} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((r, k) => (
                <tr key={k}>
                  {r.map((c, j) => (
                    <td key={j} className={j > 0 ? "num" : undefined}>
                      {c.replace(/`/g, "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (line.startsWith("- [")) {
      const items: { ok: boolean; text: string }[] = [];
      while (i < lines.length && lines[i].startsWith("- [")) {
        items.push({ ok: lines[i].startsWith("- [x]"), text: lines[i].slice(6) });
        i++;
      }
      out.push(
        <ul key={`c${i}`} className="check-list">
          {items.map((it, k) => (
            <li key={k} className={it.ok ? "ok" : "bad"}>
              {it.ok ? <Check size={15} aria-label="Passed" /> : <X size={15} aria-label="Failed" />}
              <span className="small">{it.text}</span>
            </li>
          ))}
        </ul>,
      );
      continue;
    }
    if (line.trim()) out.push(<p key={`p${i}`} className="small muted">{line.replace(/^- /, "")}</p>);
    i++;
  }
  return <>{out}</>;
}

function MetricRow({ m }: { m: Metric }) {
  const frac = m.den ? (m.num ?? 0) / m.den : null;
  const s = STATUS[m.status] ?? STATUS.info;
  return (
    <li className={`metric s-${m.status.replace(" ", "-")}`}>
      <div className="metric-text">
        <span className="metric-name">{m.name}</span>
        {m.note && <span className="tiny faint">{m.note}</span>}
      </div>
      <div className="metric-value">
        {frac !== null && (
          <span className="metric-bar" aria-hidden="true">
            <span style={{ width: `${Math.max(2, frac * 100)}%`, background: s.color }} />
          </span>
        )}
        <strong className="num">{m.value === null ? "—" : String(m.value)}</strong>
        {m.target && <span className="tiny faint num">target {m.target}</span>}
      </div>
      <StatusChip status={m.status} />
    </li>
  );
}

/** The live targets are set for Gemini working alone, with nobody checking its facts; say what a failure there means. */
function WhyLiveFails({ metrics }: { metrics: Metric[] }) {
  const fails = metrics.filter((m) => m.status === "fail").length;
  if (!fails) return null;
  return (
    <div className="hint-note evals-why">
      <Info size={16} aria-hidden="true" />
      <p>
        <strong>
          Why {fails === 1 ? "one live check fails" : `${fails} live checks fail`}.
        </strong>{" "}
        These checks measure Gemini working alone: every fact it found was accepted without anyone checking it. The app never works that way. A person checks each fact against its
        quote before the engine uses it, and with checked facts the engine matched every hand-written answer (the first section). We show the numbers as measured, so you can see
        what the review step is for.
      </p>
    </div>
  );
}

export default function Evals() {
  const [report, setReport] = useState<Report | null>(null);
  const [demos, setDemos] = useState<DemoSummary[]>([]);
  useEffect(() => {
    api.evals().then(
      (r) => setReport(r as unknown as Report),
      () => setReport({ available: false, note: "The evaluation report couldn't be loaded." }),
    );
    api.demos().then(setDemos, () => setDemos([]));
  }, []);

  const slices = useMemo(() => {
    const t = report?.totals;
    if (!t) return [];
    return [
      { key: "pass", label: "Pass", value: t.pass, color: "var(--st-prepared-fill)" },
      { key: "fail", label: "Fail", value: t.fail, color: "var(--st-blocked-fill)" },
      { key: "not run", label: "Not run (needs a Gemini key)", value: t.not_run, color: "var(--st-confirm-fill)" },
      { key: "info", label: "For context", value: t.info, color: "var(--st-notdue-fill)" },
    ];
  }, [report]);
  const judged = report?.totals ? report.totals.pass + report.totals.fail : 0;

  return (
    <div className="public-page">
      <PublicNav />
      <main id="main" className="evals-page">
        <header className="evals-hero">
          <div>
            <h1 className="two-tone">
              <span>How we know it works.</span> <span className="second">Measured, not claimed.</span>
            </h1>
            {report?.ai_mode === "live" ? (
              <p className="lede">
                Every number on this page comes from the evaluation harness, run against hand-written answers for four made-up households. This run also sent every benchmark source to
                Gemini on the free tier (<code>make eval-live</code>). Nothing here is typed in by hand, and checks that missed their target are shown as failed.
              </p>
            ) : (
              <p className="lede">
                Every number on this page comes from the evaluation harness (<code>make eval</code>), run against hand-written answers for four made-up households. Nothing here is typed
                in by hand, and the checks that need a live Gemini key say so instead of guessing.
              </p>
            )}
          </div>
          {report?.available && report.totals && (
            <div className="evals-score panel glass">
              <Donut
                slices={slices}
                size={150}
                thickness={16}
                label={`${report.totals.pass} of ${judged} checks pass`}
                center={
                  <>
                    <strong className="num">
                      {report.totals.pass}/{judged}
                    </strong>
                    <span>pass</span>
                  </>
                }
              />
              <ul className="evals-legend">
                {slices.map((s) => (
                  <li key={s.key}>
                    <i style={{ background: s.color }} aria-hidden="true" /> {s.label} <strong className="num">{s.value}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </header>

        {!report ? (
          <Spinner label="Loading the report…" />
        ) : !report.available ? (
          <p className="empty">{report.note ?? "No evaluation report yet."}</p>
        ) : (
          <>
            <div className="evals-meta small muted">
              {report.generated && <span>Generated {fmtDate(report.generated.slice(0, 10))}</span>}
              {report.ai_mode && <span>AI: {report.ai_mode}</span>}
              {report.engine && (
                <span className="num">
                  {report.engine}, rules {report.policy}
                </span>
              )}
              {report.commit && <span className="num">commit {report.commit}</span>}
            </div>
            <nav className="evals-toc" aria-label="Sections">
              {report.sections?.map((s) => (
                <a key={s.title} href={`#sec-${s.id ?? s.title}`} className="toc-chip">
                  {s.title}
                </a>
              ))}
            </nav>
            <div className="evals-sections">
              {report.sections?.map((s) => (
                <section key={s.title} className="panel solid evals-section" id={`sec-${s.id ?? s.title}`} aria-labelledby={`h-${s.id ?? s.title}`}>
                  <h2 id={`h-${s.id ?? s.title}`}>{s.title}</h2>
                  {s.summary && <p className="small muted evals-summary">{s.summary}</p>}
                  <ul className="metrics">
                    {s.metrics.map((m) => (
                      <MetricRow key={m.name} m={m} />
                    ))}
                  </ul>
                  {s.id === "live" && <WhyLiveFails metrics={s.metrics} />}
                  {s.details && s.details.length > 0 && (
                    <details className="more">
                      <summary>Details</summary>
                      <Details lines={s.details} />
                    </details>
                  )}
                </section>
              ))}
            </div>
            <p className="tiny faint evals-how">
              To reproduce: <code>make setup && make eval</code>. The live Gemini checks run with <code>make eval-live</code> and a key in <code>GEMINI_API_KEY</code>; they cost free-tier
              allowance, so they are off by default.
            </p>
          </>
        )}

        {demos.length > 0 && (
          <section className="evals-households" aria-labelledby="households-title">
            <h2 id="households-title">The households behind these numbers</h2>
            <ul className="family-grid">
              {demos.map((d) => (
                <li key={d.id} className="family-card">
                  <h3>{d.name}</h3>
                  <p className="small muted">{d.story}</p>
                  <p className="tiny faint">
                    Leaves {fmtDay(d.departure)}, {d.horizon_days} days away, {d.responsibilities} responsibilities, {d.sources} sources
                  </p>
                  <Link to={`/demo/${d.id}`} className="btn btn-ghost btn-sm family-open">
                    Open it <ArrowRight size={14} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
