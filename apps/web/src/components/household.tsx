import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Briefcase,
  Car,
  ChevronRight,
  Circle,
  FileText,
  GraduationCap,
  HeartPulse,
  Hospital,
  House,
  Plane,
  Receipt,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { Sparkline } from "./charts/Small";
import { Avatar, Modal, StateBadge } from "./ui";
import { EVENT, findingMeta, STATE } from "../lib/meta";
import { cap, fmtDay, fmtShort } from "../lib/format";
import type { Finding, HouseholdView, RespResult, State } from "../lib/types";

export const CATEGORY: Record<string, LucideIcon> = {
  bills: Receipt,
  documents: FileText,
  health: HeartPulse,
  home: House,
  income: Briefcase,
  money: Wallet,
  school: GraduationCap,
  vehicle: Car,
  work: Briefcase,
  household: House,
  care: HeartPulse,
  transport: Car,
};

export function CategoryIcon({ category, size = 18 }: { category: string; size?: number }) {
  const Icon = CATEGORY[category] ?? Circle;
  return (
    <span className="cat-icon" aria-hidden="true">
      <Icon size={size} />
    </span>
  );
}

/** The trip, as a boarding pass: who leaves, when, for how long, who is at home. */
export function BoardingPass({ h }: { h: HouseholdView }) {
  const s = h.settings;
  const r = h.analysis?.result;
  const leaver = h.people.find((p) => p.id === s.leaver)?.name ?? "Leaving";
  const home = h.people.filter((p) => p.id !== s.leaver).map((p) => p.name);
  const hospital = s.absence === "hospital";
  const plan = h.analysis?.plan;
  const end = r?.scenario.end_inclusive;
  const Icon = hospital ? Hospital : Plane;
  return (
    <article className="pass" data-tour="pass" aria-label="The absence at a glance">
      <div className="pass-main">
        <div className="pass-row">
          <div>
            <span className="pass-label">Leaving</span>
            <strong className="pass-name">{leaver}</strong>
          </div>
          <span className="pass-tag">{hospital ? "Hospital stay" : s.absence === "other" ? "Away" : "Work abroad"}</span>
        </div>
        <div className="pass-route">
          <span className="pass-code">{hospital ? "HOME" : s.airport_from || "HOME"}</span>
          <span className="pass-line" aria-hidden="true">
            <i />
            <Icon size={20} />
            <i />
          </span>
          <span className="pass-code">{hospital ? "WARD" : s.airport_to || (s.destination ? s.destination.slice(0, 3).toUpperCase() : "AWAY")}</span>
        </div>
        {s.destination && <span className="pass-dest">{s.destination}</span>}
        <dl className="pass-grid">
          <div>
            <dt>Leaves</dt>
            <dd>{fmtDay(s.departure)}</dd>
          </div>
          <div>
            <dt>Away</dt>
            <dd className="num">{s.horizon_days} days</dd>
          </div>
          <div>
            <dt>Back on</dt>
            <dd>{end ? fmtDay(end) : "—"}</dd>
          </div>
        </dl>
        <div className="pass-home">
          <span className="pass-label">At home</span>
          <span>{home.join(", ") || "Nobody added yet"}</span>
        </div>
      </div>
      <div className="pass-stub" aria-hidden="false">
        <div>
          <span className="pass-label">Ready</span>
          <strong className="num">
            {r?.summary.ready ?? 0}/{r?.summary.total ?? 0}
          </strong>
        </div>
        <div>
          <span className="pass-label">Plan</span>
          <strong className="num">{plan ? `${plan.minutes} min` : "—"}</strong>
        </div>
        <div className="pass-barcode" aria-hidden="true" />
      </div>
    </article>
  );
}

export function KpiTile({
  label,
  value,
  sub,
  icon,
  tone,
  spark,
  delta,
  to,
}: {
  label: string;
  value: ReactNode;
  sub: ReactNode;
  icon: ReactNode;
  tone: State | "brand" | "accent";
  spark?: number[];
  delta?: number | null;
  to?: string;
}) {
  const color = tone === "brand" ? "var(--brand)" : tone === "accent" ? "var(--accent-strong)" : STATE[tone].color;
  const soft = tone === "brand" ? "var(--brand-soft)" : tone === "accent" ? "var(--accent-soft)" : STATE[tone].soft;
  const inner = (
    <>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ color, background: soft }}>
          {icon}
        </span>
        <span className="kpi-label">{label}</span>
        {to && <ArrowUpRight size={16} className="kpi-go" aria-hidden="true" />}
      </div>
      <div className="kpi-value-row">
        <strong className="kpi-value num">{value}</strong>
        {delta != null && delta !== 0 && (
          <span className={`kpi-delta ${delta > 0 ? "up" : "down"}`}>
            {delta > 0 ? "▲" : "▼"} {Math.abs(delta)}
          </span>
        )}
        {spark && spark.length > 0 && <Sparkline values={spark} color={color} />}
      </div>
      <span className="kpi-sub">{sub}</span>
    </>
  );
  return to ? (
    <Link to={to} className="kpi">
      {inner}
    </Link>
  ) : (
    <div className="kpi">{inner}</div>
  );
}

export function RespRow({ r, onOpen }: { r: RespResult; onOpen: (r: RespResult) => void }) {
  const done = r.occurrences_total ? r.occurrences_ready / r.occurrences_total : 0;
  const st = STATE[r.state];
  return (
    <li>
      <button type="button" className="resp-row" onClick={() => onOpen(r)}>
        <CategoryIcon category={r.category} />
        <span className="resp-main">
          <span className="resp-label">{cap(r.label)}</span>
          <span className="resp-meta">
            {r.recurrence}
            {r.performers.length > 0 && ` · ${r.performers.map((p) => p.name).join(", ")}`}
          </span>
        </span>
        <span className="resp-progress" aria-label={`${r.occurrences_ready} of ${r.occurrences_total} dates ready`}>
          <span className="resp-track">
            <span style={{ width: `${done * 100}%`, background: st.fill }} />
          </span>
          <span className="tiny faint num">
            {r.occurrences_ready}/{r.occurrences_total}
          </span>
        </span>
        <StateBadge state={r.state} size="sm" />
        <ChevronRight size={16} className="faint" aria-hidden="true" />
      </button>
    </li>
  );
}

export function RespDetail({ r, onClose, base }: { r: RespResult | null; onClose: () => void; base: string }) {
  return (
    <Modal open={!!r} onClose={onClose} title={r ? cap(r.label) : ""} wide>
      {r && (
        <div className="stack">
          <div className="row">
            <StateBadge state={r.state} />
            <span className="small muted">{r.recurrence}</span>
          </div>
          <p className="lead-text">{r.headline}</p>
          {r.path.length > 0 && (
            <div>
              <h3 className="mini-title">How we got there</h3>
              <ol className="path">
                {r.path.map((n, i) => (
                  <li key={`${n.id}-${i}`} className={`path-node ${n.status ?? ""}`}>
                    <span className="path-kind">{n.kind}</span>
                    <span>{n.label}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div>
            <h3 className="mini-title">Every date while away</h3>
            <ul className="occ-list">
              {r.occurrences.slice(0, 24).map((o) => {
                const state: State = o.prepared ? "prepared" : o.value === "F" ? "blocked" : o.value === "U" ? "needs_confirmation" : "needs_handover";
                return (
                  <li key={o.date}>
                    <span className="occ-date num">{fmtDay(o.date)}</span>
                    <StateBadge state={state} size="sm" />
                    <span className="small muted occ-why">
                      {o.chosen ? `${o.chosen.person_name}: ${o.chosen.route_label}` : (o.reasons[0]?.message ?? "Nobody can do it yet.")}
                    </span>
                  </li>
                );
              })}
            </ul>
            {r.occurrences.length > 24 && <p className="tiny faint">and {r.occurrences.length - 24} more dates</p>}
          </div>
          <div className="row">
            <Link to={`${base}/plan`} className="btn btn-primary btn-sm">
              See the plan
            </Link>
            <Link to={`${base}/practise?r=${r.id}`} className="btn btn-ghost btn-sm">
              Practise this
            </Link>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function FindingMini({ f, base }: { f: Finding; base: string }) {
  const meta = findingMeta(f.kind);
  const Icon = meta.icon;
  return (
    <li className="finding-mini">
      <Link to={`${base}/found#${encodeURIComponent(f.id)}`}>
        <span className="fm-head">
          <span className="fm-kind">
            <Icon size={15} aria-hidden="true" /> {meta.label}
          </span>
          {f.dates[0] && <span className="fm-date num">{fmtShort(f.dates[0])}</span>}
        </span>
        <strong className="fm-title">{f.title}</strong>
        <span className="fm-sum">{f.summary}</span>
        {f.responsibilities.length > 0 && (
          <span className="fm-affects">
            {f.responsibilities.slice(0, 3).map((r) => (
              <span key={r.id} className="tag">
                {r.label}
              </span>
            ))}
          </span>
        )}
      </Link>
    </li>
  );
}

export function PersonChip({ id, name }: { id: string; name: string }) {
  return (
    <span className="person-chip">
      <Avatar id={id} name={name} size={22} />
      {name}
    </span>
  );
}

export function useRespDetail() {
  const [open, setOpen] = useState<RespResult | null>(null);
  return { open, setOpen };
}

export function eventState(status: string): State {
  return EVENT[status]?.state ?? "not_due";
}
