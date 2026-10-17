import { useEffect, useState } from "react";
import { AudioLines, ChevronDown, Printer } from "lucide-react";
import { ContinuityCard } from "../components/ContinuityCard";
import { PracticeSession } from "../components/PracticeSession";
import { Brand } from "../components/shell/Brand";
import { ThemeToggle } from "../components/shell/ThemeToggle";
import { ErrorNote, Spinner, StateBadge } from "../components/ui";
import { api, errorText } from "../lib/api";
import { cap } from "../lib/format";
import { RESULT } from "../lib/meta";
import type { HandoverView } from "../lib/types";

/** What the person staying opens from their link. The token stays in the #fragment. */
export default function Handover() {
  const [token] = useState(() => window.location.hash.replace(/^#/, ""));
  const [view, setView] = useState<HandoverView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = () => {
    if (!token) {
      setError("This link is missing its code. Ask for the link again.");
      return;
    }
    api.openHandover(token).then(
      (v) => {
        setView(v);
        setError(null);
      },
      (e) => setError(errorText(e)),
    );
  };
  useEffect(load, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="handover-page">
      <header className="handover-top">
        <Brand compact />
        <span className="grow" />
        <ThemeToggle />
      </header>
      {error && (
        <div className="center-page">
          <ErrorNote message={error} onRetry={token ? load : undefined} />
        </div>
      )}
      {!view && !error && (
        <div className="center-page">
          <Spinner label="Opening your handover…" size={22} />
        </div>
      )}
      {view && (
        <main className="handover-main" id="main">
          <section className="handover-hero">
            <h1 className="two-tone">
              <span>Hi {view.person_name}.</span> <span className="second">Here's what {view.leaver_name} handed over to you.</span>
            </h1>
            <p className="lede">Your part of the Continuity Card is below. You can practise each task here, by talking or typing, as often as you like.</p>
            <button type="button" className="btn btn-ghost" onClick={() => window.print()}>
              <Printer size={16} aria-hidden="true" /> Print my card
            </button>
          </section>

          {view.practice.length > 0 && (
            <section className="handover-practice" aria-label="Practise">
              <h2>Practise</h2>
              <ul>
                {view.practice.map((p) => {
                  const last = p.attempts[p.attempts.length - 1];
                  const isOpen = open === p.responsibility;
                  return (
                    <li key={p.responsibility} className="panel solid">
                      <button type="button" className="disclose wide" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : p.responsibility)}>
                        <AudioLines size={18} aria-hidden="true" />
                        <span className="grow">{cap(p.label)}</span>
                        {last && <StateBadge state={RESULT[last.result]?.tone ?? "needs_confirmation"} size="sm" label={RESULT[last.result]?.label} />}
                        <ChevronDown size={16} aria-hidden="true" />
                      </button>
                      {isOpen && (
                        <PracticeSession
                          scenario={p.scenario}
                          steps={p.steps}
                          personName={view.person_name}
                          liveVoice={view.live_voice}
                          grade={(body) => api.handoverPractice(token, p.responsibility, body)}
                          voiceToken={() => api.handoverVoice(token, p.responsibility)}
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
          <ContinuityCard card={view.card} forPerson={view.person_name} />
          <p className="tiny faint handover-foot">This page shows only what {view.leaver_name} chose to share with you. They can switch the link off at any time.</p>
        </main>
      )}
    </div>
  );
}
