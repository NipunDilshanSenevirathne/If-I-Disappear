import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ArrowRight,
  AudioLines,
  BrainCircuit,
  CalendarRange,
  Code2,
  Cpu,
  Hospital,
  House,
  ListChecks,
  Mic,
  Plane,
  Quote,
  ScanText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { PublicNav } from "../components/shell/PublicNav";
import { Brand } from "../components/shell/Brand";
import { Ring } from "../components/charts/Small";
import { api } from "../lib/api";
import { cap, fmtDay, fmtShort, plural } from "../lib/format";
import { FINDING, STATE } from "../lib/meta";
import type { DemoSummary } from "../lib/types";
import { useUsage } from "../state/app";

interface Metric {
  name: string;
  value: string | null;
  status: string;
  num?: number;
  den?: number;
}
interface Report {
  available: boolean;
  generated?: string;
  totals?: { pass: number; fail: number; not_run: number; info: number };
  sections?: { id?: string; title: string; metrics: Metric[] }[];
}

const ROLE_NAMES: Record<string, string> = {
  listener: "Voice notes",
  reader: "Photos and PDFs",
  extractor: "Finding facts",
  challenger: "AI review",
  grader: "Checking practice",
};

const BOARD_LABEL: Record<string, string> = {
  blocked: "Blocked",
  needs_confirmation: "Needs a check",
  needs_handover: "Handover not done",
  prepared: "Ready",
};

/** Real engine output from the sample households, shown as examples. */
const EXAMPLES: { kind: keyof typeof FINDING; text: string; who: string }[] = [
  { kind: "SHARED_DEPENDENCY", text: "Nirmala's phone number is still needed. Nothing else works yet to get messages from the school.", who: "Perera household" },
  { kind: "SCHEDULE_CLASH", text: "Sunil drives airport runs every Thursday, 03:30 to 10:00. That clashes with taking Achchi to her clinic, 6 times.", who: "Perera household" },
  { kind: "HELD_BY_LEAVER", text: "Mr Silva's number, needed to pay the school van fee, is only on Nirmala's phone.", who: "Perera household" },
  { kind: "DEADLINE_IN_ABSENCE", text: "The motorbike revenue licence expires on 31 December, and nobody at home is ready to renew it.", who: "Selvarajah household" },
  { kind: "NOT_ASKED", text: "Ask Malar: can you collect the co-op share payment?", who: "Selvarajah household" },
  { kind: "CONTRADICTION", text: "Your sources say 'Rs 6,000' or 'Rs 6,500' for the school van fee. Which is right?", who: "Perera household" },
];

function metric(report: Report | null, section: string, name: string): Metric | undefined {
  return report?.sections?.find((s) => s.id === section)?.metrics.find((m) => m.name.startsWith(name));
}

function sumMetrics(report: Report | null, section: string, prefixes: string[]): { num: number; den: number } | null {
  const ms = report?.sections?.find((s) => s.id === section)?.metrics.filter((m) => prefixes.some((p) => m.name.startsWith(p)) && m.den) ?? [];
  if (!ms.length) return null;
  return { num: ms.reduce((n, m) => n + (m.num ?? 0), 0), den: ms.reduce((n, m) => n + (m.den ?? 0), 0) };
}

function HeroBoard({ d }: { d: DemoSummary }) {
  const s = d.summary;
  const hospital = d.absence === "hospital";
  const Icon = hospital ? Hospital : Plane;
  const states = s
    ? ([
        ["blocked", s.blocked],
        ["needs_confirmation", s.needs_confirmation],
        ["needs_handover", s.needs_handover],
        ["prepared", s.ready],
      ] as const)
    : [];
  return (
    <figure className="hero-board" aria-label={`Live result for the ${d.name}`}>
      <div className="hb-top">
        <span className="hb-live">
          <span className="live-dot" aria-hidden="true" /> Live engine result
        </span>
        <span className="hb-name">{d.name}</span>
      </div>
      <div className="hb-trip">
        <div>
          <span className="hb-label">Leaving</span>
          <strong>{d.leaver}</strong>
        </div>
        <div className="hb-route" aria-label={`From ${d.airport_from ?? "home"} to ${d.airport_to ?? d.destination ?? "away"}`}>
          <span>{d.airport_from ?? "HOME"}</span>
          <i aria-hidden="true" />
          <Icon size={18} aria-hidden="true" />
          <i aria-hidden="true" />
          <span>{d.airport_to ?? "AWAY"}</span>
        </div>
        <div className="hb-right">
          <span className="hb-label">Away</span>
          <strong className="num">{d.horizon_days} days</strong>
        </div>
      </div>
      {s && (
        <div className="hb-main">
          <div className="hb-ring">
            <Ring value={s.ready} max={s.total} size={96} stroke={9} color="var(--st-prepared-fill)" label={`${s.ready} of ${s.total} ready`} />
            <div className="hb-ring-text">
              <strong className="num">
                {s.ready}/{s.total}
              </strong>
              <span>ready</span>
            </div>
          </div>
          <ul className="hb-states">
            {states.map(([k, n]) => (
              <li key={k}>
                <span className="hb-state-name">{BOARD_LABEL[k]}</span>
                <span className="hb-bar">
                  <span style={{ width: `${(100 * n) / Math.max(1, s.total)}%`, background: STATE[k].fill }} />
                </span>
                <span className="num">{n}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {d.stops && d.stops.length > 0 && (
        <div className="hb-stops">
          <span className="hb-label">What stops first</span>
          <ol>
            {d.stops.slice(0, 3).map((x) => (
              <li key={x.label}>
                <span className="hb-date num">{fmtShort(x.date)}</span>
                <span>{cap(x.label)}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {d.plan_minutes != null && s && (
        <figcaption className="hb-plan">
          <ListChecks size={16} aria-hidden="true" />
          <span>
            A <strong className="num">{d.plan_minutes}-minute</strong> plan gets{" "}
            <strong className="num">
              {d.plan_after} of {s.total}
            </strong>{" "}
            ready
          </span>
        </figcaption>
      )}
    </figure>
  );
}

function Section({ id, title, lede, children, className = "" }: { id?: string; title: ReactNode; lede?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section id={id} className={`l-section ${className}`} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="l-head">
        <h2 id={id ? `${id}-title` : undefined}>{title}</h2>
        {lede && <p className="l-lede">{lede}</p>}
      </div>
      {children}
    </section>
  );
}

export default function Landing() {
  const [demos, setDemos] = useState<DemoSummary[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const { usage } = useUsage();
  const location = useLocation();

  useEffect(() => {
    api.demos().then(setDemos, () => setDemos([]));
    api.evals().then(
      (r) => setReport(r as unknown as Report),
      () => setReport(null),
    );
  }, []);

  useEffect(() => {
    if (!location.hash) return;
    const t = window.setTimeout(() => document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    return () => window.clearTimeout(t);
  }, [location.hash]);

  const main = demos[0];
  const proof = useMemo(() => {
    if (!report?.available) return [];
    const out: { big: string; text: string }[] = [];
    const states = metric(report, "engine", "Readiness states match");
    if (states?.den) out.push({ big: `${states.num}/${states.den}`, text: "readiness states match hand-written answers across 4 households" });
    const mis = sumMetrics(report, "quotes", ["Misquote rejected", "Right words, wrong source"]);
    if (mis) out.push({ big: `${mis.num.toLocaleString()}/${mis.den.toLocaleString()}`, text: "deliberate misquotes caught before anyone sees them" });
    const day = metric(report, "router", "Judging day");
    const base = metric(report, "router", "Baseline, one model only");
    if (day?.den) out.push({ big: `${day.num}/${day.den}`, text: `AI calls answered on a simulated busy judging day on one free key${base?.den ? ` (one model alone: ${base.num})` : ""}` });
    const hostile = metric(report, "containment", "All containment checks");
    if (hostile?.den) out.push({ big: `${hostile.num}/${hostile.den}`, text: "hijacked-model attacks contained by code" });
    return out;
  }, [report]);

  const chains = usage?.chains ?? {};

  return (
    <div className="landing">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <PublicNav />
      <main id="main">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-text">
            <p className="hero-kicker">
              <House aria-hidden="true" /> For families where one person keeps the house running
            </p>
            <h1 id="hero-title" className="hero-title two-tone">
              <span>Leaving home for months?</span> <span className="second">Find what stops before you go.</span>
            </h1>
            <p className="hero-lede">
              Record how the house runs in a few voice notes and photos. If I Disappear works out, date by date, what will stop while you're away, gives you the shortest plan to
              fix it, and helps the person staying practise.
            </p>
            <div className="hero-ctas">
              <Link to="/demo?tour=1" className="pill-cta accent">
                <span>See a family's plan</span>
                <span className="pill-arrow" aria-hidden="true">
                  <ArrowRight size={18} />
                </span>
              </Link>
              <Link to="/start" className="btn btn-ghost btn-lg">
                Start your own household
              </Link>
            </div>
            <ul className="trust-row">
              <li>
                <ShieldCheck size={17} aria-hidden="true" /> Never stores passwords or PINs
              </li>
              <li>
                <Quote size={17} aria-hidden="true" /> Every fact quoted from its source
              </li>
              <li>
                <Sparkles size={17} aria-hidden="true" /> Runs on the free Gemini tier
              </li>
            </ul>
          </div>
          <div className="hero-visual">
            <div className="hero-glow" aria-hidden="true" />
            {main ? <HeroBoard d={main} /> : <div className="hero-board skeleton" aria-hidden="true" />}
            {main?.findings != null && (
              <div className="float-chip one" aria-hidden="true">
                <strong className="num">{main.findings}</strong>
                <span>problems nobody mentioned</span>
              </div>
            )}
            {main && (
              <div className="float-chip two" aria-hidden="true">
                <strong className="num">{main.sources}</strong>
                <span>voice notes, photos and PDFs, every fact quoted</span>
              </div>
            )}
          </div>
        </section>

        <section className="facts-band" aria-labelledby="why-title">
          <h2 id="why-title">Behind every departure is a household that has to keep running.</h2>
          <ul className="fact-grid">
            <li>
              <strong className="fact-num num">312,836</strong>
              <span>Sri Lankans left for work abroad in 2024, a record.</span>
              <a href="https://ft.lk/front-page/2024-sets-record-for-Sri-Lankans-going-abroad-for-work/44-771235" target="_blank" rel="noreferrer" className="fact-src">
                SLBFE, reported by Daily FT
              </a>
            </li>
            <li>
              <strong className="fact-num num">2.19 million</strong>
              <span>Filipinos worked overseas in 2024. More than half were women.</span>
              <a href="https://www.gmanetwork.com/news/pinoyabroad/dispatch/969755/ofws-grew-to-2-19m-in-2024-psa/story/" target="_blank" rel="noreferrer" className="fact-src">
                Philippine Statistics Authority, reported by GMA News
              </a>
            </li>
            <li>
              <strong className="fact-num num">USD 8.07 bn</strong>
              <span>sent home to Sri Lanka in 2025: money someone at home has to receive and manage.</span>
              <a
                href="https://bizenglish.adaderana.lk/sri-lankas-workers-remittances-surpass-usd-8-billion-for-first-time-in-history-in-2025"
                target="_blank"
                rel="noreferrer"
                className="fact-src"
              >
                Central Bank of Sri Lanka, reported by Ada Derana Biz
              </a>
            </li>
          </ul>
          <p className="facts-note">
            Bills, school fees, a parent's clinic visits, a vehicle's papers. What goes wrong in the first weeks is rarely what the person leaving forgot to write down. It's what
            nobody realised mattered.
          </p>
        </section>

        <Section
          id="finds"
          title="It finds what nobody said"
          lede="For every date of the absence it works out who would do each task, with what, and when. These come straight from the engine's results for the sample families."
        >
          <ul className="finds-grid">
            {EXAMPLES.map((e) => {
              const meta = FINDING[e.kind];
              return (
                <li key={e.kind} className="find-card">
                  <span className="find-kind">
                    <meta.icon size={16} aria-hidden="true" /> {meta.label}
                  </span>
                  <p>{e.text}</p>
                  <span className="tiny faint">{e.who}</span>
                </li>
              );
            })}
          </ul>
          <p className="small muted l-after">
            It also sets aside false alarms, with the reason: a phone number that appears next to four tasks is only flagged for the ones that really need it.
          </p>
        </Section>

        <Section id="how" title="How it works" lede="Four steps, spread over the weeks before you leave. You can stop and come back at any point.">
          <ol className="how-steps">
            <li>
              <span className="how-num num" aria-hidden="true">
                1
              </span>
              <span className="how-icon">
                <Mic size={22} aria-hidden="true" />
              </span>
              <h3>Tell it how the house runs</h3>
              <p>Talk, photograph a bill or a school notice, or type. Gemini writes it down and pulls out facts, each with its exact words.</p>
            </li>
            <li>
              <span className="how-num num" aria-hidden="true">
                2
              </span>
              <span className="how-icon">
                <ScanText size={22} aria-hidden="true" />
              </span>
              <h3>Check the facts</h3>
              <p>Accept the right ones. A fact whose words can't be found in its source can't be used at all.</p>
            </li>
            <li>
              <span className="how-num num" aria-hidden="true">
                3
              </span>
              <span className="how-icon">
                <CalendarRange size={22} aria-hidden="true" />
              </span>
              <h3>See what stops, date by date</h3>
              <p>Every day of the absence is simulated: who can do each task, with what, and when. Problems come with the reason and the date.</p>
            </li>
            <li>
              <span className="how-num num" aria-hidden="true">
                4
              </span>
              <span className="how-icon">
                <AudioLines size={22} aria-hidden="true" />
              </span>
              <h3>Fix it, then practise</h3>
              <p>The shortest plan for the time you have. The person staying explains each task back by voice and gets a one-page card for the fridge.</p>
            </li>
          </ol>
        </Section>

        <Section
          id="proof"
          className="split"
          title="The AI reads. Code decides."
          lede="Gemini listens, reads and reviews. Deterministic code decides what stops, so the same facts always give the same answer, and a hijacked model can't change a number."
        >
          <div className="proof-wrap">
            <ol className="mini-flow" aria-label="How an answer is made">
              <li className="ai">
                <BrainCircuit size={16} aria-hidden="true" /> Gemini reads a voice note or a photo
              </li>
              <li className="code">
                <Code2 size={16} aria-hidden="true" /> Code checks every quote, word for word
              </li>
              <li className="code">
                <Code2 size={16} aria-hidden="true" /> Code simulates every date of the absence
              </li>
              <li className="ai">
                <BrainCircuit size={16} aria-hidden="true" /> A second Gemini reader checks each finding
              </li>
              <li className="code">
                <Code2 size={16} aria-hidden="true" /> Code applies only checks that cite real facts
              </li>
            </ol>
            <div className="proof-grid">
              {proof.map((p) => (
                <div key={p.text} className="proof-tile">
                  <strong className="num">{p.big}</strong>
                  <span>{p.text}</span>
                </div>
              ))}
              {proof.length === 0 && <p className="small muted">The evaluation report appears here once it has been generated.</p>}
              <Link to="/evals" className="btn btn-ghost proof-link">
                See the full evaluation <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </Section>

        <Section
          id="free"
          title="Built to run on the free Gemini tier"
          lede="One free API key, several Google models. Each job has its own line of models: the best first, the next when it's busy or used up. Some allowance is always kept for every kind of job, so a busy day of photos never leaves a voice note unheard."
        >
          <div className="free-wrap">
            <dl className="chain-list">
              {Object.entries(chains).map(([role, chain]) => (
                <div key={role} className="chain-row">
                  <dt>{ROLE_NAMES[role] ?? role}</dt>
                  <dd>
                    {chain.map((c, i) => (
                      <span key={c.model} className="chain-item">
                        {i > 0 && <ArrowRight size={13} aria-hidden="true" className="faint" />}
                        <span className="model-chip">
                          <Cpu size={11} aria-hidden="true" /> {c.label}
                        </span>
                      </span>
                    ))}
                  </dd>
                </div>
              ))}
              {usage && (
                <div className="chain-row">
                  <dt>Spoken practice</dt>
                  <dd>
                    <span className="model-chip">
                      <Cpu size={11} aria-hidden="true" /> {usage.live_model.label}
                    </span>
                  </dd>
                </div>
              )}
            </dl>
            <ul className="free-points">
              <li>
                <strong>Watches every limit.</strong> Requests per minute, tokens per minute and requests per day, for each model, reset at midnight Pacific time as Google does.
              </li>
              <li>
                <strong>Never trusts a reply blindly.</strong> Every answer is checked against its schema; a broken one goes to the next model.
              </li>
              <li>
                <strong>Doesn't ask twice.</strong> Identical requests reuse the first answer, and each visitor has a fair daily share.
              </li>
              <li>
                <strong>Says what it used.</strong> Each step shows which model answered, and a live meter shows what's left today.
              </li>
            </ul>
          </div>
        </Section>

        {demos.length > 0 && (
          <Section id="households" title="Four sample families to try" lede="Every name, number and document in them is made up. Open one and look around; nothing you do there affects anyone else.">
            <ul className="family-grid">
              {demos.map((d) => {
                const s = d.summary;
                return (
                  <li key={d.id} className="family-card">
                    <div className="family-top">
                      <span className="family-kind">{d.absence === "hospital" ? <Hospital size={15} aria-hidden="true" /> : <Plane size={15} aria-hidden="true" />}</span>
                      <h3>{d.name}</h3>
                    </div>
                    <p className="small muted">{d.story}</p>
                    {s && (
                      <div className="family-bar" role="img" aria-label={`${s.ready} ready, ${s.blocked} blocked, ${s.needs_confirmation} need a check, ${s.needs_handover} handover not finished, of ${s.total}`}>
                        {(
                          [
                            ["prepared", s.ready],
                            ["needs_handover", s.needs_handover],
                            ["needs_confirmation", s.needs_confirmation],
                            ["blocked", s.blocked],
                          ] as const
                        ).map(([k, n]) => (n ? <span key={k} style={{ flex: n, background: STATE[k].fill }} /> : null))}
                      </div>
                    )}
                    <dl className="family-facts">
                      <div>
                        <dt>Leaves</dt>
                        <dd>{fmtDay(d.departure)}</dd>
                      </div>
                      <div>
                        <dt>Away</dt>
                        <dd className="num">{d.horizon_days} days</dd>
                      </div>
                      <div>
                        <dt>Would stop</dt>
                        <dd className="num">{s ? `${s.blocked} of ${s.total}` : "—"}</dd>
                      </div>
                      <div>
                        <dt>Plan</dt>
                        <dd className="num">{d.plan_minutes != null ? `${d.plan_minutes} min` : "—"}</dd>
                      </div>
                    </dl>
                    <Link to={`/demo/${d.id}`} className="btn btn-ghost btn-sm family-open">
                      Open the {d.name.replace(/^The /, "")} <ArrowRight size={14} aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Section>
        )}

        <section className="final-cta" aria-labelledby="final-title">
          <h2 id="final-title" className="two-tone">
            <span>Leaving soon?</span> <span className="second">Start with one voice note.</span>
          </h2>
          <p className="muted">It takes a minute. You'll see what it found before anything is used, and you can delete everything at any time.</p>
          <div className="hero-ctas center">
            <Link to="/start" className="pill-cta accent">
              <span>Start your household</span>
              <span className="pill-arrow" aria-hidden="true">
                <ArrowRight size={18} />
              </span>
            </Link>
            <Link to="/demo?tour=1" className="btn btn-ghost btn-lg">
              Take the tour first
            </Link>
          </div>
        </section>
      </main>
      <footer className="l-foot">
        <Brand compact />
        <p className="tiny faint">
          {plural(demos.length || 4, "sample household", "sample households")}, all made up. Built with Gemini, Gemma, Google ADK and Cloud Run. Not a substitute for legal, medical or
          financial advice.
        </p>
        <nav className="l-foot-links" aria-label="More">
          <Link to="/evals">Evaluation</Link>
          <Link to="/start">Start a household</Link>
          <Link to="/demo">Open the sample</Link>
        </nav>
      </footer>
    </div>
  );
}
