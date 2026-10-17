// Shapes returned by the API (services/api/app/engine/serialize.py and services/views.py).

export type State = "prepared" | "needs_handover" | "needs_confirmation" | "blocked" | "not_due";
export type Tri = "T" | "F" | "U";

export interface Person {
  id: string;
  name: string;
  role: string | null;
  minor: boolean;
}

export interface Entity {
  id: string;
  kind: string;
  name: string;
  aliases: string[];
  resource_kind: string | null;
  identifier: string | null;
  role: string | null;
  minor: boolean;
  generic: boolean;
  category: string | null;
  proposed: boolean;
}

export interface Source {
  id: string;
  kind: "voice" | "image" | "pdf" | "text" | "practice" | "evidence";
  title: string;
  speaker: string | null;
  speaker_name: string | null;
  text: string;
  mime_type: string | null;
  observed: string | null;
  synthetic: boolean;
  redactions: number;
  status: "ready" | "processing" | "error";
  summary: string | null;
  error: string | null;
  has_file: boolean;
  claim_count: number;
}

export interface EvidenceRef {
  source_id: string;
  quote: string;
  locator: string | null;
}

export interface Claim {
  id: string;
  predicate: string;
  subject: string;
  object: string | null;
  value: string | null;
  date: string | null;
  end_date: string | null;
  schedule: { freq: string; interval: number; weekdays: string[]; monthday: number | null; anchor: string | null } | null;
  window: { start: string; end: string } | null;
  evidence: EvidenceRef[];
  derivation: string;
  review: "unreviewed" | "accepted" | "disputed" | "superseded" | "withdrawn";
  stated_by: string | null;
  created_by: string;
  note: string | null;
  fixed: boolean;
  confidence: number | null;
  verified: boolean | null;
  issues: string[];
  source_ids: string[];
}

export interface Reason {
  code: string;
  message: string;
  kind: "hard" | "unknown" | "info";
  refs: Record<string, string>;
  claim_ids: string[];
}

export interface Occurrence {
  date: string;
  label: string;
  act_by: string;
  value: Tri;
  prepared: boolean;
  chosen: {
    route_id: string;
    route_label: string;
    person: string;
    person_name: string;
    day: string;
    window: string | null;
    missing: { code: string; text: string }[];
  } | null;
  reasons: Reason[];
}

export interface PathNode {
  kind: string;
  id: string;
  label: string;
  status?: string | null;
  claim_ids?: string[];
}

export interface RespResult {
  id: string;
  label: string;
  category: string;
  weight: number;
  state: State;
  state_text: string;
  feasibility: Tri;
  headline: string;
  first_problem: string | null;
  problem_date?: string | null;
  performers: { id: string; name: string }[];
  occurrences_total: number;
  occurrences_ready: number;
  recurrence: string;
  owners: { id: string; name: string }[];
  policy: "light" | "standard" | "critical";
  occurrences: Occurrence[];
  path: PathNode[];
  claim_ids: string[];
}

export interface Summary {
  total: number;
  ready: number;
  prepared: number;
  not_due: number;
  needs_handover: number;
  needs_confirmation: number;
  blocked: number;
  weight_total: number;
  weight_ready: number;
  ready_pct: number | null;
  occurrence_coverage: number;
  sentence: string;
}

export interface Assumption {
  id: string;
  kind: string;
  target: string;
  label: string;
  negotiable: boolean;
  claim_ids: string[];
}

export interface ScenarioInfo {
  id: string;
  label: string;
  leaver: string;
  leaver_name: string;
  start: string;
  end_exclusive: string;
  end_inclusive: string;
  days: number;
  assumptions: Assumption[];
}

export interface TimelineEvent {
  date: string;
  label: string;
  responsibility: string;
  responsibility_label: string;
  status: "ready" | "blocked" | "unknown" | "handover";
  message: string | null;
  person: string | null;
}

export interface ResultView {
  scenario: ScenarioInfo;
  world_version: number;
  engine_version: string;
  policy_version: string;
  summary: Summary;
  responsibilities: RespResult[];
  timeline: TimelineEvent[];
  diagnostics: string[];
}

export interface Considered {
  responsibility: string;
  label: string;
  verdict: "retained" | "set_aside";
  code: string;
  message: string;
  claim_ids: string[];
}

export interface Challenge {
  verdict: "uphold" | "narrow" | "question";
  explanation: string;
  drop: string[];
  because_claims: string[];
  weak_claims: string[];
  question: string | null;
  by: string;
}

export interface Finding {
  id: string;
  kind: string;
  title: string;
  summary: string;
  severity: number;
  responsibilities: { id: string; label: string }[];
  dates: string[];
  path: PathNode[];
  claim_ids: string[];
  considered: Considered[];
  assumptions: string[];
  questions: string[];
  status: string;
  challenge: Challenge | null;
  asks: { person: string; responsibility: string; question: string }[];
  rank: number;
}

export interface Step {
  id: string;
  kind: string;
  title: string;
  owner: string;
  owner_name: string;
  collaborators: { id: string; name: string }[];
  minutes: number;
  minutes_range: [number, number];
  evidence: string;
  uncertain: boolean;
  responsibility: string | null;
  note: string;
}

export interface Bundle {
  id: string;
  responsibility: string;
  responsibility_label: string;
  strategy: string;
  label: string;
  people: { id: string; name: string }[];
  minutes: number;
  covers: string[];
  leaves: string[];
  steps: Step[];
}

export interface PlanView {
  budget_minutes: number;
  label: string;
  exhaustive: boolean;
  evaluated: number;
  minutes: number;
  minutes_by_person: { id: string; name: string; minutes: number }[];
  before: Summary;
  after: Summary;
  after_states: Record<string, { state: State; state_text: string; occurrences_ready: number; occurrences_total: number }>;
  bundles: Bundle[];
  steps: Step[];
  alternatives: Bundle[];
  note: string;
}

export interface TraceStep {
  node: string;
  kind: "agent" | "code";
  ms: number;
  summary: string;
  model?: string | null;
  model_label?: string | null;
  cached?: boolean;
  skipped?: { model: string; label: string; why: string }[];
}

export interface Analysis {
  world_version: number;
  computed_at: string;
  ai_mode: string;
  models: string[] | null;
  workflow: string;
  challenge: string;
  result: ResultView;
  findings: Finding[];
  plan: PlanView;
  diagnostics: string[];
  trace: TraceStep[];
  review_trace?: TraceStep[];
  review_at?: string | null;
}

export interface ProcedureStep {
  id: string;
  text: string;
  critical: boolean;
  hint: string | null;
}

export interface Procedure {
  responsibility: string;
  version: number;
  approved: boolean;
  steps: ProcedureStep[];
  scenario_prompt: string;
}

export interface Attempt {
  id: string;
  person: string;
  responsibility: string;
  created: string | null;
  transcript: string;
  hints: string[];
  covered: string[];
  missed: string[];
  unsafe: string[];
  result: "unassisted" | "practiced_with_help" | "not_yet";
  grader: string;
  feedback: string | null;
}

export interface HandoverEvent {
  id: string;
  person: string;
  responsibility: string;
  kind: string;
  level: string;
  attempt_id: string | null;
  witness: string | null;
  note: string | null;
  created: string | null;
}

export interface LogEntry {
  at: string;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
}

export interface HistoryPoint {
  at: string;
  action: string;
  ready: number;
  total: number;
  blocked: number;
  needs_confirmation: number;
  needs_handover: number;
  weight_pct: number | null;
}

export interface ShareInfo {
  id: string;
  person: string;
  person_name: string;
  responsibilities: { id: string; label: string }[];
  created: string;
  revoked: boolean;
  opened: number;
}

export interface Settings {
  id: string;
  name: string;
  leaver: string;
  departure: string;
  destination: string | null;
  absence?: "travel" | "hospital" | "other";
  airport_from: string | null;
  airport_to: string | null;
  horizon_days: number;
  assessment_date: string;
  synthetic: boolean;
  card_entries: string[];
  in_scope: string[] | null;
  budget_minutes: number;
}

export interface HouseholdView {
  id: string;
  name: string;
  demo: boolean;
  demo_source: string | null;
  variant: string | null;
  variants: { id: string; title: string; summary: string }[];
  stages_available: string[];
  stages_applied: string[];
  version: number;
  rev: number;
  settings: Settings;
  people: Person[];
  entities: Entity[];
  sources: Source[];
  claims: Claim[];
  procedures: Procedure[];
  attempts: Attempt[];
  events: HandoverEvent[];
  analysis: Analysis | null;
  ai: { mode: string; live_voice: boolean; tier: string; models: { extract: string; review: string; live: string } | null };
  history: HistoryPoint[];
  shares: ShareInfo[];
  log: LogEntry[];
  updated: string;
}

export interface Job {
  id: string;
  household_id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  progress: TraceStep[];
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface PublicConfig {
  version: string;
  ai_mode: string;
  live_voice: boolean;
  models: { extract: string; review: string; live: string } | null;
  quota_tier: string;
  auth: string;
  max_upload_mb: number;
}

export interface DemoSummary {
  id: string;
  name: string;
  story: string;
  kind: string;
  leaver: string;
  at_home?: string[];
  destination: string | null;
  absence?: "travel" | "hospital" | "other";
  airport_from?: string | null;
  airport_to?: string | null;
  departure: string;
  horizon_days: number;
  responsibilities: number;
  sources: number;
  later_stage: boolean;
  variants: number;
  summary?: { ready: number; total: number; blocked: number; needs_confirmation: number; needs_handover: number } | null;
  plan_minutes?: number | null;
  plan_after?: number | null;
  plan_steps?: number | null;
  first_problem?: string | null;
  stops?: { label: string; date: string }[];
  findings?: number | null;
}

export interface UsageRow {
  model: string;
  label: string;
  used_today: number;
  limit_today: number | null;
  usable_today: number | null;
  left_today: number | null;
  used_this_minute: number;
  limit_per_minute: number | null;
  ok: number;
  rejected: number;
  failed: number;
  cooling_down_for: number;
  note: string;
}

export interface AiUsage {
  day: string;
  resets_at: string;
  reused_answers: number;
  models: UsageRow[];
  tier: string;
  mode: string;
  live_model: { model: string; label: string };
  chains: Record<string, { model: string; label: string; keep: number }[]>;
  visitor: { used_today: number; limit_today: number | null; left_today: number | null };
  generated: string;
}

export interface ExploreOptions {
  people: { id: string; name: string }[];
  things: { id: string; name: string; kind: string }[];
  assumptions: { id: string; label: string; negotiable: boolean }[];
  departure: string;
  days: number;
}

export interface ExploreResult {
  changes: string[];
  scenario: ScenarioInfo;
  before: Summary;
  after: Summary;
  responsibilities: {
    id: string;
    label: string;
    before: State | null;
    after: State;
    changed: boolean;
    worse: boolean;
    better: boolean;
    headline: string;
    occurrences_ready: number;
    occurrences_total: number;
  }[];
  worse: number;
  better: number;
}

export interface CardItem {
  responsibility: string;
  label: string;
  category: string;
  weight: number;
  state: State;
  who: string | null;
  when: string;
  dates: string[];
  next: string | null;
  act_by: string | null;
  route: string | null;
  key_step: string | null;
  steps: { id: string; text: string; critical: boolean }[];
  where: { kind: "place" | "contact"; item: string; where: string }[];
  on_card: boolean;
}

export interface CardView {
  household: string;
  leaver: string;
  from: string;
  to: string;
  generated: string;
  synthetic: boolean;
  summary: { ready: number; total: number };
  items: CardItem[];
  gaps: { responsibility: string; label: string; date: string; date_label: string; message: string | null }[];
  no_secrets: boolean;
}

export interface PracticeBrief {
  responsibility: string;
  label: string;
  person: string;
  person_name: string;
  scenario: string;
  step_count: number;
  key_steps: number;
  steps: { id: string; text: string; critical: boolean; hint: string | null }[];
  live_voice: boolean;
  attempts: Attempt[];
}

export interface AttemptResult {
  attempt: Attempt;
  missed_steps: { id: string; text: string; critical: boolean; hint: string | null }[];
  event?: HandoverEvent | null;
  trace: TraceStep[];
  household?: HouseholdView;
}

export interface DraftStep {
  text: string;
  critical: boolean;
  hint: string | null;
}

export interface StepsDraft {
  responsibility: string;
  label: string;
  steps: DraftStep[];
  scenario_prompt: string;
  existing: boolean;
}

export interface HandoverView {
  household: string;
  person: string;
  person_name: string;
  leaver_name: string;
  synthetic: boolean;
  card: CardView;
  practice: {
    responsibility: string;
    label: string;
    scenario: string;
    steps: { id: string; text: string; critical: boolean; hint: string | null }[];
    attempts: { id: string; result: Attempt["result"]; created: string | null; missed: string[] }[];
  }[];
  live_voice: boolean;
}

export interface SampleFile {
  household: string;
  id: string;
  title: string;
  kind: "image" | "pdf" | "voice";
  mime_type: string;
  url: string;
}

export interface NewResponsibility {
  label: string;
  category: string;
  freq: "once" | "weekly" | "monthly" | "ongoing";
  interval: number;
  weekdays: string[];
  monthday: number | null;
  date: string | null;
  window_start: string | null;
  window_end: string | null;
  usual: string | null;
  taker: string | null;
  agreed: "yes" | "unsure" | "no";
  importance: number;
  needs: { name: string; kind: string; held_by: string | null; taker_has_it: boolean }[];
  key_step: string | null;
}
