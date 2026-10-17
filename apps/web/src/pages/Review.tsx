import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, CheckCheck, ChevronDown, CircleSlash, FileText, ImageUp, Mic, PencilLine, ScanText, ShieldAlert, ShieldCheck, Type, Undo2, X } from "lucide-react";
import { claimSentence } from "../components/claims";
import { EmptyState, Meter, PageHeader, Segmented } from "../components/ui";
import { api, errorText } from "../lib/api";
import { plural } from "../lib/format";
import type { Claim, Source } from "../lib/types";
import { useLoaded, useToast } from "../state/app";

type Filter = "todo" | "accepted" | "all";

const REVIEW_LABEL: Record<Claim["review"], string> = {
  unreviewed: "To check",
  accepted: "Accepted",
  disputed: "Disputed",
  superseded: "Replaced",
  withdrawn: "Rejected",
};

function SourceIcon({ s }: { s: Source | undefined }) {
  const Icon = !s ? PencilLine : s.kind === "voice" ? Mic : s.kind === "image" ? ImageUp : s.kind === "pdf" ? FileText : Type;
  return <Icon size={16} aria-hidden="true" />;
}

export default function Review() {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const todo = h.claims.filter((c) => c.review === "unreviewed");
  const accepted = h.claims.filter((c) => c.review === "accepted").length;
  const readyToAccept = todo.filter((c) => c.verified && c.issues.length === 0).length;
  const [filter, setFilter] = useState<Filter>(todo.length ? "todo" : "all");
  const [busy, setBusy] = useState<string | null>(null);
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const sources = useMemo(() => new Map(h.sources.map((s) => [s.id, s])), [h.sources]);

  const shown = useMemo(
    () => h.claims.filter((c) => (filter === "todo" ? c.review === "unreviewed" : filter === "accepted" ? c.review === "accepted" : true)),
    [h.claims, filter],
  );
  const groups = useMemo(() => {
    const out = new Map<string, Claim[]>();
    for (const c of shown) {
      const sid = c.evidence[0]?.source_id ?? c.source_ids[0] ?? "app";
      out.set(sid, [...(out.get(sid) ?? []), c]);
    }
    return [...out.entries()];
  }, [shown]);

  const act = async (c: Claim, action: string, changes?: Record<string, unknown>) => {
    setBusy(c.id);
    try {
      setHousehold(await api.review(h.id, c.id, action, changes));
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };

  const acceptAll = async (sourceId?: string) => {
    setBusy(sourceId ?? "all");
    try {
      const out = await api.acceptVerified(h.id, sourceId);
      setHousehold(out);
      toast("Accepted every fact whose words were found in its source. The results have been updated.");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Check the facts"
        lede="Each fact shows the exact words it came from. Accept the right ones and reject the wrong ones. Only accepted facts are used to work out what stops."
        actions={
          readyToAccept > 0 ? (
            <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => void acceptAll()}>
              <CheckCheck size={16} aria-hidden="true" /> Accept {plural(readyToAccept, "checked fact", "checked facts")}
            </button>
          ) : undefined
        }
      />
      <div className="review-top panel glass">
        <div className="review-progress">
          <div className="row-between">
            <strong className="small">
              {accepted} of {h.claims.length} facts accepted
            </strong>
            <span className="tiny faint">{todo.length ? `${todo.length} to check` : "All checked"}</span>
          </div>
          <Meter value={accepted} max={Math.max(1, h.claims.length)} tone="ok" label="Facts accepted" />
        </div>
        <Segmented
          label="Show"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "todo", label: `To check (${todo.length})` },
            { value: "accepted", label: `Accepted (${accepted})` },
            { value: "all", label: "Everything" },
          ]}
        />
      </div>

      {groups.length === 0 && (
        <EmptyState
          icon={<ScanText size={22} aria-hidden="true" />}
          title={filter === "todo" ? "Nothing left to check" : "No facts here yet"}
          action={
            <Link to={`/h/${h.id}/capture`} className="btn btn-ghost">
              Add a voice note or a photo
            </Link>
          }
        >
          {filter === "todo" ? "Every fact has been looked at. New ones appear here after you add something." : "Facts appear here after Gemini reads what you add."}
        </EmptyState>
      )}

      <div className="review-groups">
        {groups.map(([sid, claims], gi) => {
          const s = sources.get(sid);
          const groupReady = claims.filter((c) => c.review === "unreviewed" && c.verified && !c.issues.length).length;
          const pending = claims.filter((c) => c.review === "unreviewed").length;
          const isOpen = opened[sid] ?? (filter === "todo" || pending > 0 || gi === 0);
          return (
            <section key={sid} className={`review-group ${isOpen ? "open" : ""}`} aria-label={s?.title ?? "Added in the app"}>
              <header className="review-group-head">
                <button type="button" className="review-group-toggle" aria-expanded={isOpen} onClick={() => setOpened((o) => ({ ...o, [sid]: !isOpen }))}>
                  <span className="cat-icon">
                    <SourceIcon s={s} />
                  </span>
                  <span className="grow">
                    <h2>{s?.title ?? "Added in the app"}</h2>
                    <span className="tiny faint">
                      {s?.speaker_name ? `${s.speaker_name}, ` : ""}
                      {plural(claims.length, "fact", "facts")}
                      {pending > 0 ? `, ${pending} to check` : ""}
                    </span>
                  </span>
                  <ChevronDown size={18} aria-hidden="true" className="review-chevron" />
                </button>
                {groupReady > 1 && sid !== "app" && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={busy !== null} onClick={() => void acceptAll(sid)}>
                    <CheckCheck size={14} aria-hidden="true" /> Accept {groupReady}
                  </button>
                )}
              </header>
              {isOpen && (
                <ul className="claim-list">
                  {claims.map((c) => (
                    <ClaimCard key={c.id} c={c} busy={busy === c.id} act={act} />
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
}

function ClaimCard({ c, busy, act }: { c: Claim; busy: boolean; act: (c: Claim, action: string, changes?: Record<string, unknown>) => Promise<void> }) {
  const { h } = useLoaded();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(c.value ?? "");
  const [date, setDate] = useState(c.date ?? "");
  const editable = c.value !== null || c.date !== null;
  const sources = new Map(h.sources.map((s) => [s.id, s]));
  const open = c.review === "unreviewed" || c.review === "disputed" || c.review === "withdrawn";

  return (
    <li className={`claim-card ${c.review}`}>
      <div className="claim-body">
        <div className="claim-chips tiny">
          <span className={`tag review-${c.review}`}>{REVIEW_LABEL[c.review]}</span>
          {c.verified === true && (
            <span className="tag ok">
              <ShieldCheck size={12} aria-hidden="true" /> Words found in the source
            </span>
          )}
          {c.verified === false && (
            <span className="tag bad">
              <ShieldAlert size={12} aria-hidden="true" /> Words not found
            </span>
          )}
          {c.derivation === "model_inference" && <span className="tag">Worked out, not said</span>}
          {c.derivation === "household_review" && <span className="tag">Edited by you</span>}
          {c.confidence != null && c.confidence < 0.6 && <span className="tag warn">Unsure</span>}
        </div>
        <p className="claim-sentence">{claimSentence(c, h)}</p>
        {c.note && <p className="tiny muted">{c.note}</p>}
        {c.issues.map((i) => (
          <p key={i} className="tiny bad-text">
            {i}
          </p>
        ))}
        {c.evidence.length > 0 && (
          <div className="slips">
            {c.evidence.map((e) => (
              <figure key={`${e.source_id}-${e.quote}`} className="slip">
                <blockquote>{e.quote}</blockquote>
                <figcaption>
                  <span>{sources.get(e.source_id)?.title ?? e.source_id}</span>
                  {e.locator && <span>{e.locator}</span>}
                </figcaption>
              </figure>
            ))}
          </div>
        )}
        {editing && (
          <form
            className="claim-edit"
            onSubmit={(e) => {
              e.preventDefault();
              const changes: Record<string, unknown> = {};
              if (c.value !== null && value.trim() && value.trim() !== c.value) changes.value = value.trim();
              if (c.date !== null && date && date !== c.date) changes.date = date;
              if (Object.keys(changes).length) void act(c, "edit", changes).then(() => setEditing(false));
              else setEditing(false);
            }}
          >
            {c.value !== null && <input className="input" aria-label="Value" value={value} maxLength={200} onChange={(e) => setValue(e.target.value)} />}
            {c.date !== null && <input className="input" type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />}
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
              Save
            </button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </form>
        )}
      </div>
      <div className="claim-actions">
        {open ? (
          <>
            <button type="button" className="btn btn-sm btn-ok" disabled={busy || c.verified === false} onClick={() => void act(c, "accept")}>
              <Check size={14} aria-hidden="true" /> Accept
            </button>
            {c.review === "unreviewed" && (
              <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => void act(c, "reject")}>
                <X size={14} aria-hidden="true" /> Reject
              </button>
            )}
            {c.review !== "unreviewed" && (
              <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => void act(c, "undo")}>
                <Undo2 size={14} aria-hidden="true" /> Undo
              </button>
            )}
          </>
        ) : c.review === "accepted" ? (
          <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => void act(c, "dispute")}>
            <CircleSlash size={14} aria-hidden="true" /> It's wrong
          </button>
        ) : (
          <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => void act(c, "undo")}>
            <Undo2 size={14} aria-hidden="true" /> Undo
          </button>
        )}
        {editable && !editing && c.review !== "superseded" && (
          <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => setEditing(true)}>
            <PencilLine size={14} aria-hidden="true" /> Edit
          </button>
        )}
      </div>
    </li>
  );
}
