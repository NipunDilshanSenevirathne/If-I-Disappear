import { useEffect, useMemo, useState } from "react";
import qrcode from "qrcode-generator";
import { Copy, ExternalLink, Link2, ShieldCheck, Trash2 } from "lucide-react";
import { Avatar, EmptyState, Field, PageHeader, Panel } from "../components/ui";
import { api, errorText } from "../lib/api";
import { cap, fmtDate } from "../lib/format";
import { useLoaded, useToast } from "../state/app";

function Qr({ text }: { text: string }) {
  const svg = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
  }, [text]);
  return <div className="qr" role="img" aria-label="QR code for the handover link" dangerouslySetInnerHTML={{ __html: svg }} />;
}

export default function Share() {
  const { h, setHousehold } = useLoaded();
  const toast = useToast();
  const adults = h.people.filter((p) => !p.minor && p.id !== h.settings.leaver);
  const results = h.analysis?.result.responsibilities ?? [];
  const [person, setPerson] = useState(adults.find((p) => p.role === "backup")?.id ?? adults[0]?.id ?? "");
  const mine = useMemo(() => results.filter((r) => r.performers.some((p) => p.id === person)).map((r) => r.id), [results, person]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setChosen(mine.length ? mine : results.map((r) => r.id));
    setLink(null);
  }, [person]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async () => {
    setBusy(true);
    try {
      const out = await api.createShare(h.id, person, chosen);
      setHousehold(out.household);
      setLink(`${window.location.origin}${out.path}`);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string) => {
    try {
      await api.revokeShare(h.id, id);
      setHousehold(await api.household(h.id));
      toast("Link switched off. Anyone who opens it now sees nothing.");
    } catch (e) {
      toast(errorText(e), "error");
    }
  };

  const active = h.shares.filter((s) => !s.revoked);

  return (
    <>
      <PageHeader
        title="Share with the person staying"
        lede="Make a private link for one person. They see only their part of the card and can practise on their own phone. They can't see sources or change anything, and you can switch the link off at any time."
      />
      <div className="share-page">
        <Panel title="Make a link" tour="share-form" tone="glass">
          {adults.length === 0 ? (
            <EmptyState title="Add the person staying first">Add an adult on the Household page, then make their link here.</EmptyState>
          ) : (
            <div className="stack">
              <Field label="Who is it for?">
                <select className="input" value={person} onChange={(e) => setPerson(e.target.value)}>
                  {adults.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
              <fieldset className="choice-group">
                <legend>What should they see?</legend>
                <div className="checklist">
                  {results.map((r) => (
                    <label key={r.id} className="check">
                      <input
                        type="checkbox"
                        checked={chosen.includes(r.id)}
                        onChange={(e) => setChosen((c) => (e.target.checked ? [...c, r.id] : c.filter((x) => x !== r.id)))}
                      />
                      <span>{cap(r.label)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <button type="button" className="btn btn-primary" disabled={busy || !chosen.length || !person} onClick={() => void create()}>
                <Link2 size={16} aria-hidden="true" /> Make the link
              </button>
              {link && (
                <div className="link-out">
                  <Qr text={link} />
                  <div className="stack-sm">
                    <span className="small muted">Send this to {adults.find((p) => p.id === person)?.name} in a private message. It's shown only once.</span>
                    <input className="input mono" readOnly value={link} onFocus={(e) => e.target.select()} aria-label="Handover link" />
                    <div className="row">
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() =>
                          void navigator.clipboard.writeText(link).then(
                            () => toast("Link copied."),
                            () => toast("Select the link and copy it.", "error"),
                          )
                        }
                      >
                        <Copy size={14} aria-hidden="true" /> Copy
                      </button>
                      <a className="btn btn-quiet btn-sm" href={link} target="_blank" rel="noreferrer">
                        <ExternalLink size={14} aria-hidden="true" /> See what they'll see
                      </a>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </Panel>
        <Panel title="Links you've made" eyebrow={`${active.length} active`}>
          {h.shares.length === 0 && <p className="small muted">No links yet.</p>}
          <ul className="share-list">
            {h.shares
              .slice()
              .reverse()
              .map((s) => (
                <li key={s.id} className={s.revoked ? "revoked" : ""}>
                  <Avatar id={s.person} name={s.person_name} size={30} />
                  <div className="share-main">
                    <strong>For {s.person_name}</strong>
                    <span className="tiny faint">
                      {s.responsibilities.map((r) => r.label).join(" · ")} · made {fmtDate(s.created)} · opened {s.opened} {s.opened === 1 ? "time" : "times"}
                    </span>
                  </div>
                  {s.revoked ? (
                    <span className="tag">Switched off</span>
                  ) : (
                    <button type="button" className="btn btn-quiet btn-sm" onClick={() => void revoke(s.id)}>
                      <Trash2 size={14} aria-hidden="true" /> Switch off
                    </button>
                  )}
                </li>
              ))}
          </ul>
          <p className="tiny faint">
            <ShieldCheck size={13} aria-hidden="true" style={{ display: "inline", verticalAlign: "-2px" }} /> Only a fingerprint of each link is stored. Copies someone already printed or saved
            can't be called back.
          </p>
        </Panel>
      </div>
    </>
  );
}
