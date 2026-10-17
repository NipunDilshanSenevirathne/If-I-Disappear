import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Hospital, Plane, Plus, Trash2 } from "lucide-react";
import { PublicNav } from "../components/shell/PublicNav";
import { Field, Segmented } from "../components/ui";
import { api, errorText, type HouseholdListItem } from "../lib/api";
import { addDays, fmtAgo, fmtDay, todayIso } from "../lib/format";
import { useToast } from "../state/app";

interface PersonRow {
  name: string;
  role: "backup" | "household" | "helper";
  minor: boolean;
}

type Absence = "travel" | "hospital" | "other";

/** A live preview of the trip, filled in as the form is typed. */
function TicketPreview({ leaver, destination, departure, days, absence, people }: { leaver: string; destination: string; departure: string; days: number; absence: Absence; people: PersonRow[] }) {
  const hospital = absence === "hospital";
  const Icon = hospital ? Hospital : Plane;
  const home = people.map((p) => p.name.trim()).filter(Boolean);
  return (
    <article className="pass preview" aria-label="Preview of the absence">
      <div className="pass-main">
        <div className="pass-row">
          <div>
            <span className="pass-label">Leaving</span>
            <strong className="pass-name">{leaver.trim() || "Your name"}</strong>
          </div>
          <span className="pass-tag">{hospital ? "Hospital stay" : absence === "other" ? "Away" : "Work abroad"}</span>
        </div>
        <div className="pass-route">
          <span className="pass-code">HOME</span>
          <span className="pass-line" aria-hidden="true">
            <i />
            <Icon size={20} />
            <i />
          </span>
          <span className="pass-code">{hospital ? "WARD" : destination.trim() ? destination.trim().slice(0, 3).toUpperCase() : "AWAY"}</span>
        </div>
        {destination.trim() && <span className="pass-dest">{destination.trim()}</span>}
        <dl className="pass-grid">
          <div>
            <dt>Leaves</dt>
            <dd>{departure ? fmtDay(departure) : "—"}</dd>
          </div>
          <div>
            <dt>Away</dt>
            <dd className="num">{days} days</dd>
          </div>
          <div>
            <dt>Back on</dt>
            <dd>{departure ? fmtDay(addDays(departure, days - 1)) : "—"}</dd>
          </div>
        </dl>
        <div className="pass-home">
          <span className="pass-label">At home</span>
          <span>{home.join(", ") || "Add the people who stay"}</span>
        </div>
      </div>
      <div className="pass-stub">
        <div>
          <span className="pass-label">Ready</span>
          <strong className="num">?</strong>
        </div>
        <div>
          <span className="pass-label">Plan</span>
          <strong className="num">—</strong>
        </div>
        <div className="pass-barcode" aria-hidden="true" />
      </div>
    </article>
  );
}

export default function Start() {
  const navigate = useNavigate();
  const toast = useToast();
  const today = todayIso();
  const [name, setName] = useState("");
  const [leaver, setLeaver] = useState("");
  const [absence, setAbsence] = useState<Absence>("travel");
  const [destination, setDestination] = useState("");
  const [departure, setDeparture] = useState(addDays(today, 21));
  const [days, setDays] = useState(90);
  const [people, setPeople] = useState<PersonRow[]>([{ name: "", role: "backup", minor: false }]);
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState<HouseholdListItem[]>([]);

  useEffect(() => {
    api.households().then(
      (list) => setMine(list.filter((x) => !x.demo).slice(0, 4)),
      () => setMine([]),
    );
  }, []);

  const update = (i: number, patch: Partial<PersonRow>) => setPeople((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  const valid = leaver.trim().length > 0 && !!departure;

  const create = async () => {
    setBusy(true);
    try {
      const h = await api.createHousehold({
        name: name.trim() || `${leaver.trim()}'s household`,
        leaver_name: leaver.trim(),
        departure,
        horizon_days: days,
        destination: destination.trim() || undefined,
        absence,
        people: people.filter((p) => p.name.trim()).map((p) => ({ ...p, name: p.name.trim() })),
      });
      navigate(`/h/${h.id}/capture`);
    } catch (e) {
      toast(errorText(e), "error");
      setBusy(false);
    }
  };

  return (
    <div className="public-page">
      <PublicNav sections={false} />
      <main id="main" className="start-page">
        <div className="start-intro">
          <h1 className="two-tone">
            <span>Set up your household.</span> <span className="second">It takes a minute.</span>
          </h1>
          <p className="lede">Who is leaving, when, and who stays. Next, you'll tell it how the house runs, by talking, taking photos or typing.</p>
        </div>

        <div className="start-grid">
          <form
            className="panel solid start-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (valid) void create();
            }}
          >
            <fieldset>
              <legend>Who is leaving, and when?</legend>
              <div className="grid-2">
                <Field label="Name of the person leaving">
                  <input className="input" value={leaver} onChange={(e) => setLeaver(e.target.value)} required maxLength={60} autoComplete="given-name" placeholder="Nirmala" />
                </Field>
                <Field label="Household name (optional)">
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="The Perera household" />
                </Field>
              </div>
              <Field label="What kind of absence?">
                <Segmented
                  label="What kind of absence"
                  value={absence}
                  onChange={setAbsence}
                  options={[
                    { value: "travel", label: "Work abroad or travel" },
                    { value: "hospital", label: "A hospital stay" },
                    { value: "other", label: "Something else" },
                  ]}
                />
              </Field>
              <div className="grid-3">
                <Field label="Leaves on">
                  <input className="input" type="date" value={departure} min={today} onChange={(e) => setDeparture(e.target.value)} required />
                </Field>
                <Field label="Days away">
                  <input
                    className="input num"
                    type="number"
                    min={7}
                    max={365}
                    value={days}
                    onChange={(e) => setDays(Math.max(7, Math.min(365, Number(e.target.value) || 7)))}
                  />
                </Field>
                <Field label={absence === "hospital" ? "Which hospital? (optional)" : "Going to (optional)"}>
                  <input className="input" value={destination} onChange={(e) => setDestination(e.target.value)} maxLength={60} placeholder={absence === "hospital" ? "General Hospital" : "Japan"} />
                </Field>
              </div>
              <input className="range" type="range" min={7} max={365} value={days} aria-label="Days away" onChange={(e) => setDays(Number(e.target.value))} />
            </fieldset>

            <fieldset>
              <legend>Who stays at home?</legend>
              <p className="tiny faint">Add the person who will take over first. You can add more people later.</p>
              {people.map((p, i) => (
                <div key={i} className="person-row">
                  <Field label={i === 0 ? "Name" : `Person ${i + 1}`}>
                    <input className="input" value={p.name} onChange={(e) => update(i, { name: e.target.value })} maxLength={60} placeholder={i === 0 ? "Sunil" : ""} />
                  </Field>
                  <Field label="Their part">
                    <select className="input" value={p.role} onChange={(e) => update(i, { role: e.target.value as PersonRow["role"] })}>
                      <option value="backup">Takes over while away</option>
                      <option value="household">Lives at home</option>
                      <option value="helper">Helps from outside</option>
                    </select>
                  </Field>
                  <label className="check small person-child">
                    <input type="checkbox" checked={p.minor} onChange={(e) => update(i, { minor: e.target.checked })} /> A child
                  </label>
                  {people.length > 1 && (
                    <button type="button" className="icon-btn" aria-label={`Remove person ${i + 1}`} onClick={() => setPeople((ps) => ps.filter((_, j) => j !== i))}>
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  )}
                </div>
              ))}
              {people.length < 12 && (
                <button type="button" className="btn btn-ghost btn-sm align-start" onClick={() => setPeople((ps) => [...ps, { name: "", role: "household", minor: false }])}>
                  <Plus size={15} aria-hidden="true" /> Add someone
                </button>
              )}
            </fieldset>

            <div className="start-submit">
              <button type="submit" className="pill-cta accent" disabled={busy || !valid}>
                <span>{busy ? "Setting up…" : "Create the household"}</span>
                <span className="pill-arrow" aria-hidden="true">
                  <ArrowRight size={18} />
                </span>
              </button>
              <span className="tiny faint">Only you can see it. You can delete it at any time.</span>
            </div>
          </form>

          <aside className="start-side">
            <TicketPreview leaver={leaver} destination={destination} departure={departure} days={days} absence={absence} people={people} />
            <div className="panel glass start-tip">
              <strong>Not ready to type your own details?</strong>
              <p className="small muted">Open a sample family first. Everything in it is made up, and a short tour shows each part.</p>
              <Link to="/demo?tour=1" className="btn btn-ghost btn-sm">
                Open the sample with the tour
              </Link>
            </div>
            {mine.length > 0 && (
              <div className="panel solid start-tip">
                <strong>Continue where you left off</strong>
                <ul className="mine-list">
                  {mine.map((m) => (
                    <li key={m.id}>
                      <Link to={`/h/${m.id}`}>{m.name}</Link>
                      <span className="tiny faint">
                        {m.summary ? `${m.summary.ready} of ${m.summary.total} ready, ` : ""}
                        {fmtAgo(m.updated)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
