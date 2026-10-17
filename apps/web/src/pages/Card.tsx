import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Printer, Share2 } from "lucide-react";
import { ContinuityCard } from "../components/ContinuityCard";
import { ErrorNote, PageHeader, Spinner } from "../components/ui";
import { api, errorText } from "../lib/api";
import type { CardView } from "../lib/types";
import { useLoaded } from "../state/app";

export default function Card() {
  const { h } = useLoaded();
  const [card, setCard] = useState<CardView | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.card(h.id).then(setCard, (e) => setError(errorText(e)));
  }, [h.id, h.rev]);
  return (
    <>
      <PageHeader
        title="Continuity Card"
        lede="One page for the fridge: who does what, when, how, and where things are. No passwords, PINs or account numbers."
        actions={
          <>
            <Link to={`/h/${h.id}/share`} className="btn btn-ghost">
              <Share2 size={16} aria-hidden="true" /> Send to someone
            </Link>
            <button type="button" className="btn btn-primary" onClick={() => window.print()} disabled={!card}>
              <Printer size={16} aria-hidden="true" /> Print the card
            </button>
          </>
        }
      />
      {error && <ErrorNote message={error} />}
      {!card && !error && <Spinner label="Making the card…" />}
      {card && <ContinuityCard card={card} />}
    </>
  );
}
