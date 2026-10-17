import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  AudioLines,
  Bell,
  CalendarDays,
  Compass,
  FlaskConical,
  IdCard,
  LayoutDashboard,
  ListChecks,
  Menu,
  Mic,
  MoreHorizontal,
  Radar,
  ScanText,
  Settings2,
  Share2,
  Telescope,
  Workflow,
  X,
} from "lucide-react";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";
import { AiPill } from "../AiAllowance";
import { DemoBar } from "../DemoBar";
import { householdTour, useTour } from "../tour/Tour";
import { useLoaded } from "../../state/app";
import { actionLabel } from "../../lib/meta";
import { fmtAgo } from "../../lib/format";

interface Item {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  badge?: number;
  end?: boolean;
}

function NavItems({ items, onNavigate }: { items: Item[]; onNavigate?: () => void }) {
  return (
    <ul className="nav-list">
      {items.map((it) => (
        <li key={it.to}>
          <NavLink to={it.to} end={it.end} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`} onClick={onNavigate}>
            <it.icon size={19} aria-hidden="true" />
            <span>{it.label}</span>
            {it.badge ? <span className="nav-badge num">{it.badge}</span> : null}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function ActivityBell() {
  const { h, pulse } = useLoaded();
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(h.log.length);
  const box = useRef<HTMLDivElement>(null);
  const unseen = Math.max(0, h.log.length - seen);
  useEffect(() => {
    if (!open) return;
    setSeen(h.log.length);
    const onDown = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, h.log.length]);
  const recent = [...h.log].reverse().slice(0, 12);
  return (
    <div className="bell-wrap" ref={box}>
      <button type="button" className={`icon-btn bell ${pulse ? "pulsed" : ""}`} aria-label={`Activity${unseen ? `, ${unseen} new` : ""}`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Bell size={18} aria-hidden="true" />
        {unseen > 0 && <span className="bell-dot" aria-hidden="true" />}
      </button>
      {open && (
        <div className="glass-pop bell-pop" role="dialog" aria-label="Recent activity">
          <strong>Recent activity</strong>
          <ul className="activity">
            {recent.map((l, i) => (
              <li key={`${l.at}-${i}`}>
                <span className="activity-what">{actionLabel(l.action)}</span>
                <span className="tiny faint">{fmtAgo(l.at)}</span>
              </li>
            ))}
            {recent.length === 0 && <li className="small muted">Nothing yet.</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { h } = useLoaded();
  const base = `/h/${h.id}`;
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();
  const tour = useTour();
  const leaver = h.people.find((p) => p.id === h.settings.leaver)?.name ?? "The person leaving";
  const findings = h.analysis?.findings.length ?? 0;
  const toReview = h.claims.filter((c) => c.review === "unreviewed").length;

  useEffect(() => setDrawer(false), [location.pathname]);

  const main: Item[] = [
    { to: base, label: "Overview", icon: LayoutDashboard, end: true },
    { to: `${base}/found`, label: "What we found", icon: Radar, badge: findings },
    { to: `${base}/explore`, label: "Explore", icon: Telescope },
    { to: `${base}/calendar`, label: "Calendar", icon: CalendarDays },
    { to: `${base}/plan`, label: "Plan", icon: ListChecks },
    { to: `${base}/practise`, label: "Practise", icon: AudioLines },
    { to: `${base}/card`, label: "Card", icon: IdCard },
  ];
  const info: Item[] = [
    { to: `${base}/capture`, label: "Capture", icon: Mic },
    { to: `${base}/review`, label: "Review facts", icon: ScanText, badge: toReview },
    { to: `${base}/share`, label: "Share", icon: Share2 },
    { to: `${base}/settings`, label: "Household", icon: Settings2 },
  ];
  const more: Item[] = [
    { to: `${base}/trace`, label: "How it was worked out", icon: Workflow },
    { to: "/evals", label: "Evaluation", icon: FlaskConical },
  ];

  const sidebar = (
    <>
      <Link to="/" className="side-brand" aria-label="If I Disappear, home">
        <Brand />
      </Link>
      <div className="side-household">
        <span className="side-hh-name">{h.name}</span>
        <span className="tiny faint">{h.demo ? "Sample household" : "Your household"}</span>
      </div>
      <nav aria-label="Main">
        <NavItems items={main} onNavigate={() => setDrawer(false)} />
        <span className="nav-group">Your information</span>
        <NavItems items={info} onNavigate={() => setDrawer(false)} />
        <span className="nav-group">Under the hood</span>
        <NavItems items={more} onNavigate={() => setDrawer(false)} />
      </nav>
      <div className="side-foot">
        <ThemeToggle withLabels />
      </div>
    </>
  );

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar glass" aria-label="Sidebar">
        {sidebar}
      </aside>
      {drawer && (
        <div className="drawer-wrap" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="drawer-scrim" onClick={() => setDrawer(false)} />
          <aside className="drawer glass-strong">
            <button type="button" className="icon-btn drawer-close" aria-label="Close menu" onClick={() => setDrawer(false)}>
              <X size={20} aria-hidden="true" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="content">
        <header className="topbar glass">
          <button type="button" className="icon-btn only-mobile" aria-label="Open menu" onClick={() => setDrawer(true)}>
            <Menu size={20} aria-hidden="true" />
          </button>
          <Link to="/" className="only-mobile topbar-brand" aria-label="If I Disappear, home">
            <Brand compact />
          </Link>
          <div className="topbar-title hide-mobile">
            <span className="topbar-hh">{h.name}</span>
            {h.demo && <span className="tag">Sample</span>}
          </div>
          <span className="grow" />
          <AiPill />
          <button type="button" className="btn btn-ghost btn-sm hide-mobile" onClick={() => tour.start(householdTour(leaver, h.demo), base)}>
            <Compass size={15} aria-hidden="true" /> Take the tour
          </button>
          <button type="button" className="icon-btn phone-only" aria-label="Take the tour" onClick={() => tour.start(householdTour(leaver, h.demo), base)}>
            <Compass size={18} aria-hidden="true" />
          </button>
          <ActivityBell />
        </header>
        {h.demo && <DemoBar />}
        <main id="main" className="main" tabIndex={-1}>
          {children}
        </main>
      </div>
      <nav className="mobile-nav glass-strong" aria-label="Quick">
        {[main[0], main[1], main[4], main[5]].map((it) => (
          <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `mnav ${isActive ? "active" : ""}`}>
            <it.icon size={20} aria-hidden="true" />
            <span>{it.label === "What we found" ? "Found" : it.label}</span>
          </NavLink>
        ))}
        <button type="button" className="mnav" onClick={() => setDrawer(true)}>
          <MoreHorizontal size={20} aria-hidden="true" />
          <span>More</span>
        </button>
      </nav>
    </div>
  );
}
