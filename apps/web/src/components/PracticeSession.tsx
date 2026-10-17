import { useEffect, useRef, useState } from "react";
import { Check, Keyboard, Lightbulb, Mic, Square, X } from "lucide-react";
import { Segmented, Spinner, StateBadge } from "./ui";
import { errorText } from "../lib/api";
import { cap } from "../lib/format";
import { RESULT } from "../lib/meta";
import type { LiveHandle, LiveState, Turn } from "../lib/live";
import type { AttemptResult } from "../lib/types";

export interface SessionStep {
  id: string;
  text: string;
  critical: boolean;
  hint: string | null;
}

/** One practice session: the situation, then talk (Gemini Live) or type, then the
 *  result step by step. Used by the household and by the person staying's own link. */
export function PracticeSession({
  scenario,
  steps,
  personName,
  liveVoice,
  grade,
  voiceToken,
  onGraded,
}: {
  scenario: string;
  steps: SessionStep[];
  personName: string;
  liveVoice: boolean;
  grade: (body: { transcript: string; coach_transcript?: string; hints_given: number; mode: string }) => Promise<AttemptResult>;
  voiceToken: () => Promise<{ token: string; model: string; api_version: string }>;
  onGraded?: (r: AttemptResult) => void;
}) {
  const [mode, setMode] = useState<"voice" | "text">(liveVoice ? "voice" : "text");
  const [text, setText] = useState("");
  const [hints, setHints] = useState(0);
  const [shownHints, setShownHints] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [live, setLive] = useState<LiveState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const handle = useRef<LiveHandle | null>(null);

  useEffect(() => () => void handle.current?.stop(), []);

  const submit = async (payload: { transcript: string; coach_transcript?: string; hints_given: number; mode: string }) => {
    setBusy(true);
    setError(null);
    try {
      const out = await grade(payload);
      setResult(out);
      onGraded?.(out);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const startVoice = async () => {
    setTurns([]);
    setResult(null);
    setError(null);
    try {
      const tok = await voiceToken();
      const { startLive } = await import("../lib/live");
      handle.current = await startLive({ token: tok.token, model: tok.model, apiVersion: tok.api_version, onTurns: setTurns, onState: setLive });
    } catch (e) {
      setLive(null);
      const denied = e instanceof DOMException && (e.name === "NotAllowedError" || e.name === "NotFoundError");
      setError(denied ? "We can't use the microphone. You can type instead." : errorText(e, "Spoken practice isn't available right now. Type instead."));
      setMode("text");
    }
  };

  const finishVoice = async () => {
    const out = await handle.current?.stop();
    handle.current = null;
    setLive("ended");
    if (out && out.me.trim()) await submit({ transcript: out.me, coach_transcript: out.partner, hints_given: 0, mode: "voice" });
  };

  const showHint = () => {
    const missed = result?.missed_steps ?? [];
    const next = missed.find((s) => s.hint && !shownHints.includes(s.hint)) ?? missed[0];
    if (!next) return;
    setShownHints((x) => [...x, next.hint ?? cap(next.text)]);
    setHints((n) => n + 1);
  };

  const talking = live === "listening" || live === "speaking" || live === "connecting";
  const keySteps = steps.filter((s) => s.critical).length;

  return (
    <div className="session">
      <div className="situation">
        <span className="eyebrow">The situation</span>
        <p className="situation-text">{scenario || `Tell us how you'll do this, from start to finish.`}</p>
        <p className="tiny faint">
          {steps.length} steps, {keySteps} of them key. The steps stay hidden while {personName} explains. Every key step has to be covered, and a hint means it counts as practised with help.
        </p>
      </div>

      <Segmented
        label="How to practise"
        value={mode}
        onChange={(m) => setMode(m)}
        options={[
          { value: "voice", label: <span className="seg-icon"><Mic size={15} aria-hidden="true" /> Talk</span> },
          { value: "text", label: <span className="seg-icon"><Keyboard size={15} aria-hidden="true" /> Type</span> },
        ]}
      />
      {mode === "voice" && !liveVoice && <p className="small muted">Spoken practice needs live AI (a Gemini key). Type the explanation instead.</p>}

      {mode === "voice" && liveVoice ? (
        <div className="voice">
          <button
            type="button"
            className={`orb ${talking ? "live" : ""} ${live === "speaking" ? "speaking" : ""}`}
            onClick={() => (talking ? void finishVoice() : void startVoice())}
            aria-label={talking ? "Finish and check" : "Start talking"}
          >
            {talking ? <Square size={34} aria-hidden="true" /> : <Mic size={40} aria-hidden="true" />}
          </button>
          <span className="small muted" aria-live="polite">
            {live === "connecting"
              ? "Connecting…"
              : live === "listening"
                ? "Listening…"
                : live === "speaking"
                  ? "Your practice partner is speaking"
                  : live === "ended"
                    ? "Practice finished"
                    : "Tap to start talking. Your practice partner will set the scene."}
          </span>
          {turns.length > 0 && (
            <div className="bubbles">
              {turns.map((t, i) => (
                <div key={i} className={`bubble ${t.who === "me" ? "me" : ""}`}>
                  <span className="tiny faint">{t.who === "me" ? personName : "Practice partner"}</span>
                  {t.text}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="type-practice">
          <label className="field">
            <span className="field-label">Explain what you'll do</span>
            <textarea className="input textarea" rows={6} value={text} maxLength={8000} onChange={(e) => setText(e.target.value)} placeholder="First I'll… then… If something goes wrong, I'll…" />
          </label>
          {shownHints.map((h) => (
            <p key={h} className="hint-note">
              <Lightbulb size={16} aria-hidden="true" /> {h}
            </p>
          ))}
          <div className="row">
            <button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => void submit({ transcript: text, hints_given: hints, mode: "text" })}>
              <Check size={16} aria-hidden="true" /> Check my explanation
            </button>
            {result && result.attempt.result === "not_yet" && (
              <button type="button" className="btn btn-ghost" onClick={showHint}>
                <Lightbulb size={15} aria-hidden="true" /> Show a hint
              </button>
            )}
            {hints > 0 && <span className="tiny faint">{hints === 1 ? "1 hint used" : `${hints} hints used`}</span>}
          </div>
        </div>
      )}

      {busy && <Spinner label="Checking the explanation…" />}
      {error && <p className="error-text">{error}</p>}

      {result && (
        <div className="result" aria-live="polite">
          <div className="result-head">
            <StateBadge state={RESULT[result.attempt.result]?.tone ?? "needs_confirmation"} label={RESULT[result.attempt.result]?.label ?? result.attempt.result} />
            <span className="tiny faint">Checked by {result.attempt.grader === "keyword" ? "the offline checker" : result.attempt.grader === "gemini" ? "Gemini" : result.attempt.grader}</span>
          </div>
          {result.attempt.feedback && <p>{result.attempt.feedback}</p>}
          <ul className="step-checks">
            {steps.map((s) => {
              const ok = result.attempt.covered.includes(s.id);
              return (
                <li key={s.id} className={ok ? "ok" : "miss"}>
                  {ok ? <Check size={17} aria-label="Covered" /> : <X size={17} aria-label="Missed" />}
                  <span>
                    {ok || result.attempt.result !== "not_yet" ? s.text : (s.hint ?? "A step you'll want to remember")}
                    {s.critical && <strong className="key-mark"> key step</strong>}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
