import type { ReactNode } from "react";
import { Quote } from "lucide-react";
import { cap, fmtDate } from "../lib/format";
import type { Claim, HouseholdView } from "../lib/types";

const WEEKDAYS: Record<string, string> = { MO: "Mon", TU: "Tue", WE: "Wed", TH: "Thu", FR: "Fri", SA: "Sat", SU: "Sun" };

function scheduleText(c: Claim): string {
  const s = c.schedule;
  if (!s) return "";
  if (s.freq === "monthly") return `every month on day ${s.monthday ?? ""}`.trim();
  if (s.freq === "weekly") {
    const days = s.weekdays.map((d) => WEEKDAYS[d] ?? d).join(", ");
    const every = s.interval === 2 ? "every second" : s.interval > 2 ? `every ${s.interval}th` : "every";
    return `${every} ${days || "week"}${s.anchor ? ` from ${fmtDate(s.anchor)}` : ""}`;
  }
  if (s.freq === "once") return s.anchor ? `on ${fmtDate(s.anchor)}` : "once";
  if (s.freq === "yearly") return s.anchor ? `every year on ${fmtDate(s.anchor)}` : "every year";
  if (s.freq === "ongoing") return "all the time";
  return s.freq;
}

/** A claim as a plain sentence, built from entity names (the claim is the data, not this text). */
export function claimSentence(c: Claim, h: HouseholdView): string {
  const names = new Map(h.entities.map((e) => [e.id, e.name]));
  const S = names.get(c.subject) ?? c.subject;
  const O = c.object ? (names.get(c.object) ?? c.object) : "";
  const V = c.value ?? "";
  const W = c.window ? `${c.window.start}–${c.window.end}` : "";
  const D = c.date ? fmtDate(c.date) : "";
  switch (c.predicate) {
    case "DOES":
      return `${S} does this now: ${O.toLowerCase()}.`;
    case "CAN_DO":
      return V === "yes" ? `${S} can ${O.toLowerCase()}.` : V === "no" ? `${S} can't ${O.toLowerCase()}.` : `Not asked yet: can ${S} ${O.toLowerCase()}?`;
    case "IMPORTANCE":
      return `How much "${S}" matters: ${V} of 3.`;
    case "SCHEDULE":
      return `${cap(S)}: ${scheduleText(c)}${W ? `, ${W}` : ""}.`;
    case "LEAD_TIME":
      return `${cap(S)} needs ${V} days' notice.`;
    case "KEY_STEP":
      return `Key step for "${S}": ${V}.`;
    case "HANDOVER_LEVEL":
      return `Handover level for "${S}": ${V}.`;
    case "AMOUNT":
      return `Amount for "${S}": ${V}.`;
    case "ROUTE":
      return `One way to ${S.toLowerCase()}: ${O}.`;
    case "ROUTE_NEEDS":
      return `"${cap(S)}" needs ${O}.`;
    case "ROUTE_NEEDS_VALID":
      return `"${cap(S)}" needs ${O} to be valid.`;
    case "ROUTE_NEEDS_FACT":
      return `"${cap(S)}" works only if: ${O}.`;
    case "ROUTE_PERFORMER":
      return `Only ${O} can do "${S}".`;
    case "ROUTE_WINDOW":
      return `"${cap(S)}" takes ${W}.`;
    case "ROUTE_FLEXIBLE":
      return `"${cap(S)}" can be done up to ${V} days early.`;
    case "ROUTE_WEEKDAYS":
      return `"${cap(S)}" only on ${V}.`;
    case "NEEDS":
      return `"${cap(S)}" needs ${O}.`;
    case "NEEDS_VALID":
      return `"${cap(S)}" needs ${O} to be valid.`;
    case "HOLDS":
      return `${S} has ${O}.`;
    case "STORED_ON":
      return `${cap(S)} is kept on ${O}.`;
    case "SHARED_WITH":
      return `${cap(S)} is shared with ${O}.`;
    case "REQUIRES_RESOURCE":
      return `${cap(S)} needs ${O}.`;
    case "NOTIFIES":
      return `${cap(S)} is the reminder for "${O}".`;
    case "MENTIONED_ON":
      return `${cap(S)} is printed on ${O}.`;
    case "VALID_UNTIL":
      return `${cap(S)} is valid until ${D}.`;
    case "RENEWS":
      return `"${cap(S)}" renews ${O}.`;
    case "STOPS_DURING_ABSENCE":
      return `${cap(S)} will stop during the absence (${V}).`;
    case "BUSY":
      return `${S} is busy ${scheduleText(c)}${W ? `, ${W}` : ""}: ${V}${c.fixed ? " (can't be moved)" : ""}.`;
    case "UNAVAILABLE":
      return `${S} is away from ${D}${c.end_date ? ` to ${fmtDate(c.end_date)}` : ""}: ${V}.`;
    case "FREE_ON":
      return `${S} will be free on ${D}.`;
    case "FACT":
      return V === "yes" ? `True: ${S}.` : V === "no" ? `Not true yet: ${S}.` : `Not known yet: ${S}.`;
    case "ENABLES":
      return `How to make it true that ${S}: ${V}.`;
    case "KNOWS_SECRET":
      return `${S} knows a secret for ${O}. It is never stored here.`;
    default:
      return `${c.predicate} ${S} ${O} ${V}`.trim();
  }
}

export function QuoteSlips({ claims, h, limit }: { claims: Claim[]; h: HouseholdView; limit?: number }) {
  const sources = new Map(h.sources.map((s) => [s.id, s]));
  const refs = claims.flatMap((c) => c.evidence.map((e) => ({ c, e })));
  const seen = new Set<string>();
  const unique = refs.filter(({ e }) => {
    const k = `${e.source_id}|${e.quote}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  const shown = limit ? unique.slice(0, limit) : unique;
  if (shown.length === 0) return <p className="small muted">Decided in the app (no quote).</p>;
  return (
    <div className="slips">
      {shown.map(({ c, e }) => (
        <figure key={`${c.id}-${e.source_id}-${e.quote}`} className="slip">
          <Quote size={14} aria-hidden="true" className="slip-mark" />
          <blockquote>{e.quote}</blockquote>
          <figcaption>
            <span>{sources.get(e.source_id)?.title ?? e.source_id}</span>
            {e.locator && <span>{e.locator}</span>}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

/** Highlight the quotes of the given claims inside a source text (whitespace-insensitive). */
export function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const ranges: [number, number][] = [];
  for (const q of quotes) {
    const pattern = q
      .trim()
      .split(/\s+/)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/['\u2018\u2019]/g, "['\u2018\u2019]"))
      .join("\\s+");
    if (!pattern) continue;
    const m = new RegExp(pattern).exec(text);
    if (m) ranges.push([m.index, m.index + m[0].length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const out: ReactNode[] = [];
  let pos = 0;
  ranges.forEach(([a, b], i) => {
    if (a < pos) return;
    out.push(text.slice(pos, a));
    out.push(
      <mark key={i} className="hl">
        {text.slice(a, b)}
      </mark>,
    );
    pos = b;
  });
  out.push(text.slice(pos));
  return <>{out}</>;
}
