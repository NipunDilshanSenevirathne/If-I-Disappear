import { authHeaders, forgetSession } from "./auth";
import type {
  AiUsage,
  AttemptResult,
  CardView,
  DemoSummary,
  ExploreOptions,
  ExploreResult,
  HandoverView,
  HouseholdView,
  Job,
  NewResponsibility,
  PlanView,
  PracticeBrief,
  PublicConfig,
  SampleFile,
  ShareInfo,
  StepsDraft,
  DraftStep,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown, form?: FormData, retried = false, anonymous = false): Promise<T> {
  const headers: Record<string, string> = anonymous ? {} : { ...(await authHeaders()) };
  let payload: BodyInit | undefined;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 401 && !retried && !anonymous && (await forgetSession())) {
    // the saved visitor session expired or the server's key changed: start a new one once
    return request<T>(method, path, body, form, true);
  }
  if (!res.ok) {
    let message = `Something went wrong (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, message);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export interface HouseholdListItem {
  id: string;
  name: string;
  demo: boolean;
  updated: string;
  summary: { ready: number; total: number } | null;
}

export const api = {
  config: () => request<PublicConfig>("GET", "/api/config"),
  demos: () => request<DemoSummary[]>("GET", "/api/demos"),
  evals: () => request<Record<string, unknown>>("GET", "/api/evals"),
  usage: () => request<AiUsage>("GET", "/api/ai/usage"),
  samples: () => request<SampleFile[]>("GET", "/api/samples", undefined, undefined, false, true),

  startDemo: (reset = false, household?: string) => request<HouseholdView>("POST", "/api/demo", { reset, household: household ?? null }),
  demoStage: (id: string, stage: "capture" | "after_handover") => request<HouseholdView>("POST", `/api/demo/${id}/stage`, { stage }),
  demoVariant: (id: string, variant: string | null) => request<HouseholdView>("POST", `/api/demo/${id}/variant`, { variant }),

  households: () => request<HouseholdListItem[]>("GET", "/api/households"),
  createHousehold: (body: {
    name: string;
    leaver_name: string;
    departure: string;
    horizon_days: number;
    destination?: string;
    absence?: "travel" | "hospital" | "other";
    people: { name: string; role: string; minor: boolean }[];
  }) => request<HouseholdView>("POST", "/api/households", body),
  household: (id: string) => request<HouseholdView>("GET", `/api/households/${id}`),
  pulse: (id: string) => request<{ rev: number; updated: string; history: number }>("GET", `/api/households/${id}/pulse`),
  patchSettings: (id: string, body: Record<string, unknown>) => request<HouseholdView>("PATCH", `/api/households/${id}/settings`, body),
  addPerson: (id: string, body: { name: string; role: string; minor: boolean }) => request<HouseholdView>("POST", `/api/households/${id}/people`, body),
  deleteHousehold: (id: string) => request<{ deleted: string }>("DELETE", `/api/households/${id}`),
  exportHousehold: (id: string) => request<Record<string, unknown>>("GET", `/api/households/${id}/export`),

  addSource: (id: string, form: FormData) => request<{ job: Job; source_id: string }>("POST", `/api/households/${id}/sources`, undefined, form),
  reextract: (id: string, sourceId: string) => request<{ job: Job; source_id: string }>("POST", `/api/households/${id}/sources/${sourceId}/extract`),
  deleteSource: (id: string, sourceId: string) => request<HouseholdView>("DELETE", `/api/households/${id}/sources/${sourceId}`),
  review: (id: string, claimId: string, action: string, changes?: Record<string, unknown>) =>
    request<HouseholdView>("POST", `/api/households/${id}/claims/${claimId}`, { action, changes }),
  acceptVerified: (id: string, sourceId?: string) =>
    request<HouseholdView>("POST", `/api/households/${id}/claims-accept-verified`, { source_id: sourceId ?? null }),
  addResponsibility: (id: string, body: NewResponsibility) =>
    request<{ added: { responsibility: string; source: string; claims: string[] }; household: HouseholdView }>(
      "POST",
      `/api/households/${id}/responsibilities`,
      body,
    ),
  setScope: (id: string, responsibility: string, include: boolean) =>
    request<HouseholdView>("POST", `/api/households/${id}/scope`, { responsibility, include }),

  analyze: (id: string) => request<{ job: Job }>("POST", `/api/households/${id}/analyze`, {}),
  plan: (id: string, budget: number) => request<PlanView>("POST", `/api/households/${id}/plan`, { budget_minutes: budget }),
  exploreOptions: (id: string) => request<ExploreOptions>("GET", `/api/households/${id}/explore`),
  explore: (id: string, body: { also_away: string[]; unavailable: string[]; keep_using: string[]; days?: number | null; departure?: string | null }) =>
    request<ExploreResult>("POST", `/api/households/${id}/explore`, body),
  answer: (id: string, findingId: string, body: Record<string, unknown>) =>
    request<{ changes: string[]; household: HouseholdView }>("POST", `/api/households/${id}/findings/${findingId}/answer`, body),
  evidence: (id: string, form: FormData) =>
    request<{ recorded: { changes: string[] }; household: HouseholdView }>("POST", `/api/households/${id}/evidence`, undefined, form),

  practice: (id: string, responsibility: string, person: string) =>
    request<PracticeBrief>("GET", `/api/households/${id}/practice/${responsibility}?person=${encodeURIComponent(person)}`),
  liveToken: (id: string, responsibility: string, person: string) =>
    request<{ token: string; model: string; expires_at: string; api_version: string }>("POST", `/api/households/${id}/practice/${responsibility}/token`, {
      person,
    }),
  attempt: (id: string, responsibility: string, body: { person: string; transcript: string; coach_transcript?: string; hints_given: number; mode: string }) =>
    request<AttemptResult & { household: HouseholdView }>("POST", `/api/households/${id}/practice/${responsibility}/attempts`, body),
  procedureDraft: (id: string, responsibility: string) => request<StepsDraft>("GET", `/api/households/${id}/procedures/${responsibility}`),
  saveProcedure: (id: string, responsibility: string, body: { steps: DraftStep[]; scenario_prompt: string }) =>
    request<HouseholdView>("PUT", `/api/households/${id}/procedures/${responsibility}`, body),
  card: (id: string) => request<CardView>("GET", `/api/households/${id}/card`),

  shares: (id: string) => request<ShareInfo[]>("GET", `/api/households/${id}/shares`),
  createShare: (id: string, person: string, responsibilities: string[]) =>
    request<{ id: string; token: string; path: string; shares: ShareInfo[]; household: HouseholdView }>("POST", `/api/households/${id}/shares`, {
      person,
      responsibilities,
    }),
  revokeShare: (id: string, shareId: string) => request<ShareInfo[]>("DELETE", `/api/households/${id}/shares/${shareId}`),

  // the person staying, through their handover link (no session needed)
  openHandover: (token: string) => request<HandoverView>("POST", "/api/handover/open", { token }, undefined, false, true),
  handoverPractice: (token: string, responsibility: string, body: { transcript: string; coach_transcript?: string; hints_given: number }) =>
    request<AttemptResult>("POST", "/api/handover/practice", { token, responsibility, ...body }, undefined, false, true),
  handoverVoice: (token: string, responsibility: string) =>
    request<{ token: string; model: string; expires_at: string; api_version: string }>(
      "POST",
      "/api/handover/voice",
      { token, responsibility },
      undefined,
      false,
      true,
    ),

  job: (jobId: string) => request<Job>("GET", `/api/jobs/${jobId}`),
  fileUrl: (id: string, sourceId: string) => `/api/households/${id}/sources/${sourceId}/file`,
};

export async function fetchFile(url: string): Promise<string> {
  const res = await fetch(url, { headers: await authHeaders() });
  if (!res.ok) throw new ApiError(res.status, "File not available");
  return URL.createObjectURL(await res.blob());
}

export async function waitForJob(jobId: string, onProgress?: (job: Job) => void, timeoutMs = 300_000): Promise<Job> {
  const start = Date.now();
  let delay = 500;
  for (;;) {
    const job = await api.job(jobId);
    onProgress?.(job);
    if (job.status === "done" || job.status === "error") return job;
    if (Date.now() - start > timeoutMs) throw new ApiError(504, "This is taking longer than expected. It will keep running; check back in a minute.");
    await new Promise((r) => setTimeout(r, delay));
    delay = Math.min(1600, delay + 150);
  }
}

export function errorText(e: unknown, fallback = "Something went wrong."): string {
  return e instanceof ApiError ? e.message : e instanceof Error && e.message ? e.message : fallback;
}
