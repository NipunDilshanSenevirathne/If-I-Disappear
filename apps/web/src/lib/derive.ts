// Numbers for the charts, derived from what the engine returned. No new judgement here:
// every count comes straight from the analysis.

import type { WeekDatum } from "../components/charts/WeekBars";
import type { Slice } from "../components/charts/Donut";
import type { TrendPoint } from "../components/charts/TrendChart";
import { actionLabel, STATE } from "./meta";
import { addDays, fmtShort, fmtTime } from "./format";
import type { Analysis, HistoryPoint, Summary } from "./types";

export function weeksOf(a: Analysis): WeekDatum[] {
  const s = a.result.scenario;
  const weeks: WeekDatum[] = [];
  const n = Math.ceil(s.days / 7);
  for (let i = 0; i < n; i++) {
    const from = addDays(s.start, i * 7);
    weeks.push({ key: from, label: fmtShort(from), sub: `Week ${i + 1} · from ${fmtShort(from)}`, ready: 0, handover: 0, unknown: 0, blocked: 0 });
  }
  for (const e of a.result.timeline) {
    const idx = Math.floor((Date.parse(`${e.date}T00:00:00`) - Date.parse(`${s.start}T00:00:00`)) / (7 * 86_400_000));
    const w = weeks[idx];
    if (!w) continue;
    if (e.status === "ready") w.ready++;
    else if (e.status === "handover") w.handover++;
    else if (e.status === "unknown") w.unknown++;
    else w.blocked++;
  }
  return weeks;
}

export function worstWeek(weeks: WeekDatum[]): number {
  let best = 0;
  let score = -1;
  weeks.forEach((w, i) => {
    const v = w.blocked * 100 + w.unknown * 10 + w.handover;
    if (v > score) {
      score = v;
      best = i;
    }
  });
  return best;
}

export function stateSlices(s: Summary): Slice[] {
  return [
    { key: "prepared", label: "Ready", value: s.prepared + s.not_due, color: STATE.prepared.fill },
    { key: "needs_handover", label: "Handover not finished", value: s.needs_handover, color: STATE.needs_handover.fill },
    { key: "needs_confirmation", label: "Needs a check", value: s.needs_confirmation, color: STATE.needs_confirmation.fill },
    { key: "blocked", label: "Blocked", value: s.blocked, color: STATE.blocked.fill },
  ];
}

export function trendPoints(history: HistoryPoint[]): TrendPoint[] {
  return history.map((p, i) => ({
    key: `${p.at}-${i}`,
    label: actionLabel(p.action),
    when: i === 0 ? "Start" : fmtTime(p.at),
    ready: p.ready,
    total: p.total,
  }));
}

export function daysUntil(iso: string, today: string): number {
  return Math.round((Date.parse(`${iso}T00:00:00`) - Date.parse(`${today}T00:00:00`)) / 86_400_000);
}
