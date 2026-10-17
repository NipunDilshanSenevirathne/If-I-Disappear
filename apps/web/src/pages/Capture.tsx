import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Cpu,
  FileText,
  ImageUp,
  Mic,
  PencilLine,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Type,
  UploadCloud,
  X,
} from "lucide-react";
import { AddResponsibility } from "../components/AddResponsibility";
import { Highlighted } from "../components/claims";
import { EmptyState, Field, JobProgress, PageHeader, Panel, Spinner } from "../components/ui";
import { api, errorText, fetchFile, waitForJob } from "../lib/api";
import { fmtDate, plural } from "../lib/format";
import { clock, toWav16k, useRecorder } from "../lib/recorder";
import type { SampleFile, Source, TraceStep } from "../lib/types";
import { useLoaded, useToast, useUsage } from "../state/app";

type Mode = "talk" | "file" | "type" | "form";
const MAX_SECONDS = 240;

const MODES: { id: Mode; label: string; blurb: string; icon: typeof Mic }[] = [
  { id: "talk", label: "Talk", blurb: "Record a voice note", icon: Mic },
  { id: "file", label: "Photo or PDF", blurb: "A bill, a notice, a card", icon: ImageUp },
  { id: "type", label: "Type", blurb: "Write a note", icon: Type },
  { id: "form", label: "By hand", blurb: "A short form, no AI", icon: PencilLine },
];

const IDEAS = [
  "What do you pay each month, and how?",
  "Who do you call when something breaks?",
  "Where are the important papers kept?",
  "What happens at school each week?",
  "Which medicines are collected, and when?",
  "What runs out or renews soon?",
];

interface Outcome {
  ok: boolean;
  text: string;
  questions: string[];
  added: number;
}

export default function Capture() {
  const { h, refresh, setHousehold } = useLoaded();
  const toast = useToast();
  const usage = useUsage();
  const [params, setParams] = useSearchParams();
  const initial = (params.get("mode") === "form" ? "form" : params.get("mode") ?? "talk") as Mode;
  const [mode, setMode] = useState<Mode>(MODES.some((m) => m.id === initial) ? initial : "talk");
  const adults = h.people.filter((p) => !p.minor);
  const [speaker, setSpeaker] = useState(h.settings.leaver);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const consentBox = useRef<HTMLInputElement>(null);
  // a recording made before the box was ticked is kept here, never thrown away
  const [held, setHeld] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [samples, setSamples] = useState<SampleFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const recorder = useRecorder();
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const live = h.ai.mode === "live";
  const needsConsent = live && mode !== "form";
  const base = `/h/${h.id}`;

  useEffect(() => {
    api.samples().then(setSamples, () => setSamples([]));
  }, []);

  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const choose = (m: Mode) => {
    setMode(m);
    setParams(m === "talk" ? {} : { mode: m }, { replace: true });
  };

  const onTabKey = (e: ReactKeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = (i + (e.key === "ArrowRight" ? 1 : MODES.length - 1)) % MODES.length;
    choose(MODES[next].id);
    tabs.current[next]?.focus();
  };

  const askConsent = () => {
    toast("First tick the box to say this can be read by Google's Gemini models.", "error");
    consentBox.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    consentBox.current?.focus();
  };

  const startRecording = () => {
    if (needsConsent && !consent) return askConsent();
    setHeld(null);
    void recorder.start();
  };

  const send = async (payload: { file?: File; text?: string; title: string }) => {
    if (needsConsent && !consent) {
      if (payload.file && payload.file.type.startsWith("audio/") && mode === "talk") setHeld(payload.file);
      askConsent();
      return;
    }
    setHeld(null);
    const form = new FormData();
    form.set("title", payload.title.slice(0, 120));
    if (speaker) form.set("speaker", speaker);
    if (payload.text) form.set("text", payload.text);
    if (payload.file) form.set("file", payload.file);
    form.set("consent", consent || !live ? "true" : "false");
    setBusy(true);
    setSteps([]);
    setOutcome(null);
    try {
      const { job } = await api.addSource(h.id, form);
      await refresh();
      const done = await waitForJob(job.id, (j) => setSteps(j.progress));
      setSteps(done.progress);
      if (done.status === "error") {
        setOutcome({ ok: false, text: done.error ?? "This source couldn't be read.", questions: [], added: 0 });
      } else {
        const r = (done.result ?? {}) as { added?: number; merged?: number; summary?: string; questions?: string[] };
        const added = r.added ?? 0;
        const merged = r.merged ?? 0;
        const found =
          added || merged
            ? `Found ${plural(added, "new fact", "new facts")}${merged ? ` and ${plural(merged, "fact", "facts")} you already had` : ""}.`
            : "No new facts in this one.";
        setOutcome({ ok: true, text: `${found} ${r.summary ?? ""}`.trim(), questions: (r.questions ?? []).filter(Boolean).slice(0, 3), added });
      }
      setTitle("");
      setText("");
      setFile(null);
      await refresh();
      usage.refresh();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const stopAndSend = async () => {
    const blob = await recorder.stop();
    if (!blob || blob.size === 0) return;
    let upload: Blob = blob;
    try {
      upload = await toWav16k(blob);
    } catch {
      /* send the original recording */
    }
    const ext = upload.type === "audio/wav" ? "wav" : upload.type.includes("mp4") ? "m4a" : "webm";
    await send({ file: new File([upload], `voice-note.${ext}`, { type: upload.type }), title: title || "Voice note" });
  };

  useEffect(() => {
    if (recorder.recording && recorder.seconds >= MAX_SECONDS) void stopAndSend();
  }, [recorder.recording, recorder.seconds]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!recorder.stoppedByItself) return;
    toast("The microphone stopped, so what was recorded so far is being added.");
    void stopAndSend();
  }, [recorder.stoppedByItself]); // eslint-disable-line react-hooks/exhaustive-deps

  const trySample = async (s: SampleFile) => {
    try {
      const res = await fetch(s.url);
      if (!res.ok) throw new Error("The sample file isn't available.");
      const blob = await res.blob();
      const name = s.url.split("/").pop() ?? `${s.id}`;
      await send({ file: new File([blob], name, { type: s.mime_type }), title: s.title });
    } catch (e) {
      toast(errorText(e), "error");
    }
  };

  const chain = (role: string) => (usage.usage?.chains?.[role] ?? []).map((c) => c.label);
  const readers = mode === "talk" ? chain("listener") : mode === "file" ? chain("reader") : chain("extractor");
  const sources = useMemo(() => [...h.sources].filter((s) => s.kind !== "practice").reverse(), [h.sources]);
  const toReview = h.claims.filter((c) => c.review === "unreviewed").length;

  return (
    <>
      <PageHeader
        title="Add what you know"
        lede="Talk, take a photo, or type. Gemini reads it and pulls out facts, each with the exact words it came from. Nothing is used until you've checked it."
        actions={
          toReview > 0 ? (
            <Link to={`${base}/review`} className="btn btn-primary">
              Check {plural(toReview, "new fact", "new facts")} <ArrowRight size={16} aria-hidden="true" />
            </Link>
          ) : undefined
        }
      />
      <div className="capture-page">
        <div className="capture-main">
          <div className="mode-tiles" role="tablist" aria-label="How do you want to add it?">
            {MODES.map((m, i) => (
              <button
                key={m.id}
                ref={(el) => {
                  tabs.current[i] = el;
                }}
                type="button"
                role="tab"
                id={`tab-${m.id}`}
                aria-selected={mode === m.id}
                aria-controls="capture-panel"
                tabIndex={mode === m.id ? 0 : -1}
                className={`mode-tile ${mode === m.id ? "on" : ""}`}
                onClick={() => choose(m.id)}
                onKeyDown={(e) => onTabKey(e, i)}
              >
                <span className="mode-icon">
                  <m.icon size={22} aria-hidden="true" />
                </span>
                <strong>{m.label}</strong>
                <span className="tiny muted">{m.blurb}</span>
              </button>
            ))}
          </div>

          <section className="panel glass capture-panel" id="capture-panel" role="tabpanel" aria-labelledby={`tab-${mode}`} data-tour="capture">
            {mode !== "form" && (
              <div className="grid-2">
                <Field label={mode === "talk" ? "Who is talking?" : "Who is adding it?"}>
                  <select className="input" value={speaker} onChange={(e) => setSpeaker(e.target.value)}>
                    {adults.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Name it (optional)">
                  <input
                    className="input"
                    value={title}
                    maxLength={120}
                    placeholder={mode === "talk" ? "Monthly bills" : mode === "file" ? "Water bill" : "Notes about school"}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </Field>
              </div>
            )}

            {mode === "talk" && (
              <div className="recorder">
                <div className={`rec-stage ${recorder.recording ? "on" : ""}`}>
                  <span className="rec-ring" style={{ transform: `scale(${1 + recorder.level * 0.45})` }} aria-hidden="true" />
                  {!recorder.recording ? (
                    <button type="button" className="rec-button" disabled={busy} onClick={startRecording} aria-label="Start recording">
                      <Mic size={34} aria-hidden="true" />
                    </button>
                  ) : (
                    <button type="button" className="rec-button stop" onClick={() => void stopAndSend()} aria-label="Stop and add the voice note">
                      <Square size={28} aria-hidden="true" />
                    </button>
                  )}
                </div>
                <div className="rec-info" aria-live="polite">
                  {recorder.recording ? (
                    <>
                      <strong className="rec-time num">
                        <span className="rec-dot" aria-hidden="true" /> {clock(recorder.seconds)}
                        <span className="faint"> / {clock(MAX_SECONDS)}</span>
                      </strong>
                      <span className="small muted">Talk normally. Press stop when you're done.</span>
                      <button type="button" className="btn btn-quiet btn-sm" onClick={() => void recorder.cancel()}>
                        <X size={14} aria-hidden="true" /> Throw this one away
                      </button>
                    </>
                  ) : held ? (
                    <>
                      <strong>Your recording is kept.</strong>
                      <span className="small muted">Tick the box below, then send it.</span>
                      <span className="row">
                        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void send({ file: held, title: title || "Voice note" })}>
                          <Sparkles size={14} aria-hidden="true" /> Send the recording
                        </button>
                        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setHeld(null)}>
                          <X size={14} aria-hidden="true" /> Throw it away
                        </button>
                      </span>
                    </>
                  ) : (
                    <>
                      <strong>Press the button and talk for a minute or two.</strong>
                      <span className="small muted">Talk about a normal month at home. Short notes work best: one subject each.</span>
                    </>
                  )}
                  {recorder.error && (
                    <p className="notice small" role="alert">
                      {recorder.error === "denied"
                        ? "The microphone is blocked. Allow it in the browser's address bar, or type instead."
                        : "This browser can't record here. Type the note instead."}
                    </p>
                  )}
                </div>
                <div className="ideas" aria-label="Ideas for what to talk about">
                  <span className="tiny faint">Not sure what to say? Try one:</span>
                  <ul>
                    {IDEAS.map((idea) => (
                      <li key={idea} className="idea">
                        {idea}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {mode === "file" && (
              <div className="stack">
                <label
                  className={`dropzone ${dragging ? "over" : ""} ${file ? "has-file" : ""}`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    const f = e.dataTransfer.files?.[0];
                    if (f) setFile(f);
                  }}
                >
                  <input
                    type="file"
                    className="sr-only"
                    accept="image/png,image/jpeg,image/webp,image/heic,application/pdf,audio/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                  {preview ? (
                    <img src={preview} alt="" className="drop-preview" />
                  ) : (
                    <span className="drop-icon">{file ? <FileText size={28} aria-hidden="true" /> : <UploadCloud size={28} aria-hidden="true" />}</span>
                  )}
                  <strong>{file ? file.name : "Drop a photo or a PDF here, or choose one"}</strong>
                  <span className="tiny muted">
                    {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "JPG, PNG or PDF up to 15 MB. A voice recording works here too."}
                  </span>
                </label>
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={busy || !file} onClick={() => file && void send({ file, title: title || file.name.replace(/\.[^.]+$/, "") })}>
                    <Sparkles size={16} aria-hidden="true" /> Read it
                  </button>
                  {file && (
                    <button type="button" className="btn btn-quiet" onClick={() => setFile(null)}>
                      Choose another
                    </button>
                  )}
                </div>
                {samples.length > 0 && (
                  <div className="samples">
                    <div className="row-between">
                      <strong className="small">No document to hand? Try a sample.</strong>
                      <span className="tiny faint">Made-up papers from the sample family</span>
                    </div>
                    <ul className="sample-grid">
                      {samples.map((s) => (
                        <li key={`${s.household}-${s.id}`}>
                          <button type="button" className="sample-tile" disabled={busy} onClick={() => void trySample(s)}>
                            <span className="sample-thumb">
                              {s.kind === "image" ? <img src={s.url} alt="" loading="lazy" /> : <FileText size={26} aria-hidden="true" />}
                            </span>
                            <span className="sample-title">{s.title}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {mode === "type" && (
              <div className="stack">
                <Field label="Your note" hint={`${text.length.toLocaleString()} of 20,000 characters`}>
                  <textarea
                    className="input textarea"
                    value={text}
                    maxLength={20000}
                    rows={8}
                    placeholder="On the 10th of every month I pay the electricity bill on the bank app. The bill comes by post and I keep it in the top drawer of the steel cupboard…"
                    onChange={(e) => setText(e.target.value)}
                  />
                </Field>
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={busy || text.trim().length < 12} onClick={() => void send({ text, title: title || "Note" })}>
                    <Sparkles size={16} aria-hidden="true" /> Find the facts
                  </button>
                </div>
              </div>
            )}

            {mode === "form" && <AddResponsibility h={h} onAdded={setHousehold} />}

            {mode !== "form" && (
              <div className="capture-foot">
                <p className="secret-note small">
                  <ShieldCheck size={16} aria-hidden="true" />
                  <span>
                    Never say or show a PIN, password or full account number. If one slips in, it's removed before anything is saved, and the card never shows one.
                  </span>
                </p>
                {needsConsent && (
                  <label className="check consent">
                    <input ref={consentBox} type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                    <span>
                      This can be sent to Google's Gemini models to be read.{" "}
                      {h.ai.tier === "free" && <span className="faint">On the free tier, Google may use what it reads to improve its products.</span>}
                    </span>
                  </label>
                )}
                {!live && (
                  <p className="tiny faint">
                    This server is running without a Gemini key, so it can only read the sample documents. New voice notes and notes are saved but not read.
                  </p>
                )}
                {live && readers.length > 0 && (
                  <p className="tiny faint reader-chain">
                    <Cpu size={13} aria-hidden="true" /> Read by {readers[0]}
                    {readers.length > 1 && <>, or {readers.slice(1).join(", then ")} if it's busy</>}.
                  </p>
                )}
              </div>
            )}
          </section>

          {(busy || steps.length > 0 || outcome) && (
            <Panel title={busy ? "Reading it now…" : "Done"} tone="solid" className="job-panel">
              <div aria-live="polite">
                <JobProgress steps={steps} running={busy} />
                {outcome && (
                  <div className={`outcome ${outcome.ok ? "ok" : "bad"}`}>
                    <p>{outcome.text}</p>
                    {outcome.questions.length > 0 && (
                      <ul className="outcome-qs">
                        {outcome.questions.map((q) => (
                          <li key={q} className="small muted">
                            {q}
                          </li>
                        ))}
                      </ul>
                    )}
                    {outcome.ok && outcome.added > 0 && (
                      <Link to={`${base}/review`} className="btn btn-primary btn-sm">
                        Check the new facts <ArrowRight size={14} aria-hidden="true" />
                      </Link>
                    )}
                  </div>
                )}
              </div>
            </Panel>
          )}
        </div>

        <Panel className="capture-side" title="Sources" eyebrow={`${sources.length} added`}>
          {sources.length === 0 ? (
            <EmptyState icon={<Mic size={22} aria-hidden="true" />} title="Nothing added yet">
              Your voice notes, photos and notes will be listed here, with what was found in each.
            </EmptyState>
          ) : (
            <ul className="source-list">
              {sources.map((s) => (
                <SourceItem key={s.id} s={s} />
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}

function SourceItem({ s }: { s: Source }) {
  const { h, refresh, setHousehold } = useLoaded();
  const toast = useToast();
  const [img, setImg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const isImage = s.has_file && (s.mime_type ?? "").startsWith("image/");

  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    if (isImage)
      fetchFile(api.fileUrl(h.id, s.id)).then(
        (u) => {
          url = u;
          if (alive) setImg(u);
          else URL.revokeObjectURL(u);
        },
        () => undefined,
      );
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [h.id, s.id, isImage]);

  const quotes = h.claims.flatMap((c) => c.evidence.filter((e) => e.source_id === s.id).map((e) => e.quote));
  const Icon = s.kind === "voice" ? Mic : s.kind === "image" ? ImageUp : s.kind === "pdf" ? FileText : Type;

  const reread = async () => {
    setBusy(true);
    try {
      const { job } = await api.reextract(h.id, s.id);
      const done = await waitForJob(job.id);
      const r = done.result as { added: number; merged: number } | null;
      toast(done.status === "done" && r ? `Read again: ${plural(r.added, "new fact", "new facts")}.` : (done.error ?? "It couldn't be read again."), done.status === "done" ? "ok" : "error");
      await refresh();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      setHousehold(await api.deleteSource(h.id, s.id));
      toast(`Removed "${s.title}" and the facts that only it supported.`);
    } catch (e) {
      toast(errorText(e), "error");
      setBusy(false);
    }
  };

  return (
    <li className={`source-item ${s.status}`}>
      <div className="source-thumb">{img ? <img src={img} alt="" /> : <Icon size={20} aria-hidden="true" />}</div>
      <div className="source-body">
        <div className="source-head">
          <strong>{s.title}</strong>
          {s.status === "processing" && <Spinner size={14} label="Reading" />}
        </div>
        <div className="source-meta tiny">
          {s.speaker_name && <span className="muted">{s.speaker_name}</span>}
          {s.observed && <span className="faint">{fmtDate(s.observed)}</span>}
          {s.status === "error" && <span className="tag bad">Couldn't read</span>}
          {s.status === "ready" && <span className="tag">{plural(s.claim_count, "fact", "facts")}</span>}
          {s.redactions > 0 && <span className="tag ok">{plural(s.redactions, "secret removed", "secrets removed")}</span>}
          {s.synthetic && <span className="tag">Sample</span>}
        </div>
        {s.summary && <p className="small muted source-summary">{s.summary}</p>}
        {s.error && <p className="tiny bad-text">{s.error}</p>}
        {s.text && (
          <details className="more">
            <summary>{s.kind === "voice" ? "What was said" : "What was read"}</summary>
            <div className="source-text">
              <Highlighted text={s.text} quotes={quotes} />
            </div>
          </details>
        )}
        {s.kind !== "evidence" && (
          <div className="row source-actions">
            {!confirming ? (
              <>
                <button type="button" className="btn btn-quiet btn-sm" disabled={busy || s.status === "processing"} onClick={() => void reread()}>
                  <RefreshCw size={14} className={busy ? "spin" : ""} aria-hidden="true" /> Read again
                </button>
                <button type="button" className="btn btn-quiet btn-sm danger" disabled={busy} onClick={() => setConfirming(true)}>
                  <Trash2 size={14} aria-hidden="true" /> Remove
                </button>
              </>
            ) : (
              <>
                <span className="small">Remove it and the facts that came only from it?</span>
                <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => void remove()}>
                  Remove
                </button>
                <button type="button" className="btn btn-quiet btn-sm" onClick={() => setConfirming(false)}>
                  Keep it
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
