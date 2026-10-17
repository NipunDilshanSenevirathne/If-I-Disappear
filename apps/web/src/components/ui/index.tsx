import { useEffect, useId, useRef, type ReactNode } from "react";
import { ArrowRight, Check, CircleAlert, Cpu, LoaderCircle, RefreshCw, X } from "lucide-react";
import { avatarColor, initials } from "../../lib/format";
import { STATE, STEP_NAMES } from "../../lib/meta";
import type { State, TraceStep } from "../../lib/types";

export function StateBadge({ state, size = "md", label }: { state: State; size?: "sm" | "md"; label?: string }) {
  const meta = STATE[state];
  const Icon = meta.icon;
  return (
    <span className={`state-badge ${size}`} style={{ color: meta.color, background: meta.soft }}>
      <Icon size={size === "sm" ? 13 : 15} aria-hidden="true" strokeWidth={2.4} />
      {label ?? meta.label}
    </span>
  );
}

export function Avatar({ id, name, size = 32 }: { id: string; name: string; size?: number }) {
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, fontSize: Math.max(11, size * 0.38), background: avatarColor(id) }}
      title={name}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

export function Spinner({ label, size = 18 }: { label?: string; size?: number }) {
  return (
    <span className="spinner" role="status">
      <LoaderCircle size={size} className="spin" aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function Panel({
  title,
  eyebrow,
  actions,
  children,
  className = "",
  id,
  tour,
  tone = "solid",
}: {
  title?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  tour?: string;
  tone?: "solid" | "glass" | "flat";
}) {
  const headingId = useId();
  return (
    <section className={`panel ${tone} ${className}`} id={id} data-tour={tour} aria-labelledby={title ? headingId : undefined}>
      {(title || actions) && (
        <header className="panel-head">
          <div className="panel-titles">
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            {title && <h2 id={headingId}>{title}</h2>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, lede, actions, tour }: { title: ReactNode; lede?: ReactNode; actions?: ReactNode; tour?: string }) {
  return (
    <header className="page-header" data-tour={tour}>
      <div className="page-titles">
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <div className="empty-icon">{icon}</div>}
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-note" role="alert">
      <CircleAlert size={18} aria-hidden="true" />
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={onRetry}>
          <RefreshCw size={14} aria-hidden="true" /> Try again
        </button>
      )}
    </div>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
  size = "md",
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  return (
    <div className={`segmented ${size}`} role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className={value === o.value ? "on" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

/** A pill button with a round arrow badge, used for the main call to action. */
export function PillLink({ children, onClick, href, tone = "accent" }: { children: ReactNode; onClick?: () => void; href?: string; tone?: "accent" | "ink" }) {
  const inner = (
    <>
      <span>{children}</span>
      <span className="pill-arrow" aria-hidden="true">
        <ArrowRight size={18} />
      </span>
    </>
  );
  if (href)
    return (
      <a className={`pill-cta ${tone}`} href={href}>
        {inner}
      </a>
    );
  return (
    <button type="button" className={`pill-cta ${tone}`} onClick={onClick}>
      {inner}
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const headingId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""}`}
      aria-labelledby={headingId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <div className="modal-inner">
          <header className="modal-head">
            <h2 id={headingId}>{title}</h2>
            <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="modal-body">{children}</div>
          {footer && <footer className="modal-foot">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}

/** The steps of a workflow as they run, with the Google model that answered each AI step. */
export function JobProgress({ steps, running }: { steps: TraceStep[]; running: boolean }) {
  return (
    <ol className="job-steps">
      {steps.map((s, i) => (
        <li key={`${s.node}-${i}`} className={s.kind}>
          <span className="job-dot" aria-hidden="true">
            {s.node === "fallback" ? <CircleAlert size={14} /> : <Check size={14} />}
          </span>
          <div className="job-text">
            <strong>{STEP_NAMES[s.node] ?? s.node}</strong>
            {s.model_label && (
              <span className="model-chip">
                <Cpu size={12} aria-hidden="true" />
                {s.model_label}
                {s.cached ? " · reused" : ""}
              </span>
            )}
            {s.summary && <span className="job-summary">{s.summary.replaceAll("_", " ")}</span>}
            {s.skipped && s.skipped.length > 0 && (
              <span className="job-skipped">Skipped: {s.skipped.map((x) => `${x.label} (${x.why})`).join(", ")}</span>
            )}
          </div>
          <span className="job-ms num">{s.ms ? `${(s.ms / 1000).toFixed(1)} s` : ""}</span>
        </li>
      ))}
      {running && (
        <li className="running">
          <span className="job-dot" aria-hidden="true">
            <LoaderCircle size={14} className="spin" />
          </span>
          <div className="job-text">
            <strong>Working…</strong>
          </div>
        </li>
      )}
    </ol>
  );
}

export function Meter({ value, max, tone = "brand", label }: { value: number; max: number; tone?: "brand" | "accent" | "ok" | "warn" | "bad"; label: string }) {
  const pct = max > 0 ? Math.min(100, (100 * value) / max) : 0;
  return (
    <div className={`meter ${tone}`} role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}
