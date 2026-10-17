import { MapPin, Phone, ShieldCheck, TriangleAlert } from "lucide-react";
import { CategoryIcon } from "./household";
import { StateBadge } from "./ui";
import { LampMark } from "./shell/Brand";
import { cap, fmtDay } from "../lib/format";
import type { CardView } from "../lib/types";

/** The one-page card for the fridge. Built by code from the engine's results; no secrets. */
export function ContinuityCard({ card, forPerson }: { card: CardView; forPerson?: string }) {
  return (
    <article className="ccard" data-tour="card" aria-label="Continuity Card">
      <header className="ccard-head">
        <div className="ccard-brand">
          <LampMark size={34} />
          <div>
            <strong>Continuity Card</strong>
            <span className="small muted">{card.household}</span>
          </div>
        </div>
        <div className="ccard-away">
          <span className="small muted">{forPerson ? `For ${forPerson}` : "For everyone at home"}</span>
          <strong>
            {card.leaver} is away {fmtDay(card.from)} – {fmtDay(card.to)}
          </strong>
          <span className="tiny faint num">
            {card.summary.ready} of {card.summary.total} ready · made {fmtDay(card.generated)}
          </span>
        </div>
      </header>

      <ol className="ccard-items">
        {card.items.map((it) => (
          <li key={it.responsibility} className="ccard-item">
            <div className="ccard-item-head">
              <CategoryIcon category={it.category} />
              <h3>{cap(it.label)}</h3>
              <StateBadge state={it.state} size="sm" />
            </div>
            <dl className="ccard-facts">
              <div>
                <dt>Who</dt>
                <dd>{it.who ?? "Nobody yet"}</dd>
              </div>
              <div>
                <dt>When</dt>
                <dd>
                  {cap(it.when)}
                  {it.next && <span className="faint"> · next {it.next}</span>}
                  {it.act_by && <span className="faint"> · act by {fmtDay(it.act_by)}</span>}
                </dd>
              </div>
              {it.route && (
                <div>
                  <dt>How</dt>
                  <dd>{it.route}</dd>
                </div>
              )}
            </dl>
            {it.steps.length > 0 && (
              <ol className="ccard-steps">
                {it.steps.map((s) => (
                  <li key={s.id} className={s.critical ? "key" : ""}>
                    {s.text}
                    {s.critical && <span className="key-mark"> Don't miss</span>}
                  </li>
                ))}
              </ol>
            )}
            {it.where.length > 0 && (
              <ul className="ccard-where">
                {it.where.map((w, i) => (
                  <li key={i}>
                    {w.kind === "place" ? <MapPin size={14} aria-hidden="true" /> : <Phone size={14} aria-hidden="true" />}
                    {cap(w.item)} <span className="faint">{w.kind === "place" ? "kept in" : "saved on"}</span> {w.where}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>

      {card.gaps.length > 0 && (
        <section className="ccard-gaps">
          <h3>
            <TriangleAlert size={16} aria-hidden="true" /> Still open
          </h3>
          <ul>
            {card.gaps.slice(0, 8).map((g, i) => (
              <li key={`${g.responsibility}-${g.date}-${i}`}>
                <strong>{g.date_label}</strong> · {cap(g.label)}
                {g.message && <span className="muted"> — {g.message}</span>}
              </li>
            ))}
            {card.gaps.length > 8 && <li className="faint">and {card.gaps.length - 8} more dates</li>}
          </ul>
        </section>
      )}
      <footer className="ccard-foot">
        <ShieldCheck size={15} aria-hidden="true" /> This card never shows passwords, PINs, account numbers or full phone numbers.
        {card.synthetic && <span className="faint"> Sample household: every name and number is made up.</span>}
      </footer>
    </article>
  );
}
