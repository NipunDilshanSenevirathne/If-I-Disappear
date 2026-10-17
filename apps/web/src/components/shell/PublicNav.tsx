import { Link } from "react-router-dom";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

/** The top bar of the public pages (landing, start, evaluation). */
export function PublicNav({ sections = true }: { sections?: boolean }) {
  return (
    <header className="pub-nav glass">
      <Link to="/" className="pub-brand" aria-label="If I Disappear, home">
        <Brand />
      </Link>
      {sections && (
        <nav className="pub-links" aria-label="On this site">
          <Link to={{ pathname: "/", hash: "#how" }}>How it works</Link>
          <Link to={{ pathname: "/", hash: "#finds" }}>What it finds</Link>
          <Link to={{ pathname: "/", hash: "#free" }}>Free tier</Link>
          <Link to="/evals">Evaluation</Link>
        </nav>
      )}
      <span className="grow" />
      <ThemeToggle />
      <Link to="/demo?tour=1" className="btn btn-primary btn-sm pub-cta">
        Open the sample
      </Link>
    </header>
  );
}
