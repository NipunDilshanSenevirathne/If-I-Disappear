// What each readiness state, finding kind and evidence kind is called and looks like.
// Colour is never the only signal: every state has a word and an icon too.

import {
  AlertOctagon,
  BellOff,
  CalendarClock,
  CheckCircle2,
  CircleDashed,
  CircleHelp,
  Clock3,
  Eye,
  GitCompareArrows,
  Hand,
  MessageCircleQuestion,
  Moon,
  Repeat2,
  Split,
  type LucideIcon,
} from "lucide-react";
import type { State } from "./types";

export const STATE: Record<State, { label: string; short: string; color: string; fill: string; soft: string; icon: LucideIcon; order: number }> = {
  blocked: {
    label: "Blocked",
    short: "Blocked",
    color: "var(--st-blocked)",
    fill: "var(--st-blocked-fill)",
    soft: "var(--st-blocked-soft)",
    icon: AlertOctagon,
    order: 0,
  },
  needs_confirmation: {
    label: "Needs a check",
    short: "Check",
    color: "var(--st-confirm)",
    fill: "var(--st-confirm-fill)",
    soft: "var(--st-confirm-soft)",
    icon: CircleHelp,
    order: 1,
  },
  needs_handover: {
    label: "Handover not finished",
    short: "Handover",
    color: "var(--st-handover)",
    fill: "var(--st-handover-fill)",
    soft: "var(--st-handover-soft)",
    icon: Hand,
    order: 2,
  },
  prepared: {
    label: "Ready",
    short: "Ready",
    color: "var(--st-prepared)",
    fill: "var(--st-prepared-fill)",
    soft: "var(--st-prepared-soft)",
    icon: CheckCircle2,
    order: 3,
  },
  not_due: {
    label: "Nothing due",
    short: "Not due",
    color: "var(--st-notdue)",
    fill: "var(--st-notdue-fill)",
    soft: "var(--st-notdue-soft)",
    icon: Moon,
    order: 4,
  },
};

/** Timeline events use a smaller set of statuses. */
export const EVENT: Record<string, { label: string; state: State }> = {
  ready: { label: "Ready", state: "prepared" },
  handover: { label: "Handover not finished", state: "needs_handover" },
  unknown: { label: "Needs a check", state: "needs_confirmation" },
  blocked: { label: "Blocked", state: "blocked" },
};

export const FINDING: Record<string, { label: string; icon: LucideIcon; blurb: string }> = {
  SHARED_DEPENDENCY: { label: "Still needed while away", icon: BellOff, blurb: "Something that stops when the person leaves is still needed at home." },
  HELD_BY_LEAVER: { label: "Held by the person leaving", icon: Eye, blurb: "A thing or a contact that only the person leaving has." },
  SCHEDULE_CLASH: { label: "Clash", icon: Split, blurb: "The person taking over is busy when it has to happen." },
  DEADLINE_IN_ABSENCE: { label: "Deadline while away", icon: CalendarClock, blurb: "Something runs out or falls due during the absence." },
  DEADLINE_BEFORE_DEPARTURE: { label: "Deadline before leaving", icon: Clock3, blurb: "Something has to be done before the person leaves." },
  NOT_ASKED: { label: "Not asked yet", icon: MessageCircleQuestion, blurb: "Nobody has asked the person who is meant to take over." },
  CONTRADICTION: { label: "Sources disagree", icon: GitCompareArrows, blurb: "Two sources say different things." },
};

export function findingMeta(kind: string) {
  return FINDING[kind] ?? { label: kind.replaceAll("_", " ").toLowerCase(), icon: CircleDashed, blurb: "" };
}

export const EVIDENCE_KINDS: { id: string; label: string }[] = [
  { id: "AGREEMENT", label: "They agreed" },
  { id: "PHOTO", label: "A photo" },
  { id: "SCREENSHOT", label: "A screenshot" },
  { id: "SELF_REPORT", label: "They told me it's done" },
  { id: "PROVIDER_CONFIRMATION", label: "The provider confirmed" },
  { id: "DOCUMENT", label: "The new document" },
  { id: "APP", label: "Done in the app" },
];

export const RESULT: Record<string, { label: string; tone: State }> = {
  unassisted: { label: "Explained without help", tone: "prepared" },
  practiced_with_help: { label: "Explained with a hint", tone: "needs_handover" },
  not_yet: { label: "Not yet", tone: "needs_confirmation" },
};

export const STEP_NAMES: Record<string, string> = {
  route_source: "Sorting the source",
  listener: "Listening",
  after_listen: "Removing secrets from the transcript",
  reader: "Reading",
  after_read: "Removing secrets from the reading",
  text_ready: "Preparing the text",
  extractor: "Finding facts",
  verify_and_resolve: "Checking every quote",
  compile_claims: "Building the household model",
  evaluate_scenario: "Simulating the absence",
  discover_findings: "Looking for what nobody said",
  build_challenge: "Preparing the second reading",
  challenger: "Second reader (AI review)",
  apply_challenge: "Applying the review",
  plan_preparation: "Planning the fixes",
  build_prompt: "Preparing",
  grader: "Checking the explanation",
  decide_result: "Deciding the result",
  fallback: "Fallback",
};

export const CATEGORY_ICON: Record<string, LucideIcon> = {
  recurring: Repeat2,
};

export const ACTION_LABEL: Record<string, string> = {
  "demo.loaded": "Sample loaded",
  "demo.week_later": "A week later",
  "household.create": "Household created",
  "source.add": "Source added",
  "source.extract": "New facts found",
  "source.error": "A source couldn't be read",
  "source.delete": "Source removed",
  "claim.accept": "Fact accepted",
  "claim.reject": "Fact rejected",
  "claim.dispute": "Fact disputed",
  "claim.undo": "Review undone",
  "claim.edit": "Fact edited",
  "claim.accept_verified": "Checked facts accepted",
  "analysis.run": "AI review",
  "finding.answer": "Question answered",
  "evidence.record": "Step done",
  "practice.attempt": "Practice",
  "responsibility.add": "Added by hand",
  "scope.change": "Scope changed",
  "settings.update": "Settings changed",
  "person.add": "Person added",
  "procedure.approve": "Steps approved",
  "share.create": "Link made",
  "share.revoke": "Link switched off",
};

export function actionLabel(action: string): string {
  if (action.startsWith("demo.variant:")) return "What if";
  return ACTION_LABEL[action] ?? action.replace(/[._]/g, " ");
}
