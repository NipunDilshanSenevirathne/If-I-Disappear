import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { Brand } from "./components/shell/Brand";
import { TourProvider } from "./components/tour/Tour";
import { ErrorNote, Spinner } from "./components/ui";
import { api, errorText } from "./lib/api";
import { ThemeProvider, ToastProvider, UsageProvider } from "./state/app";
import Landing from "./pages/Landing";

const HouseholdApp = lazy(() => import("./HouseholdApp"));
const Start = lazy(() => import("./pages/Start"));
const Evals = lazy(() => import("./pages/Evals"));
const Handover = lazy(() => import("./pages/Handover"));

function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading-page">
      <Spinner label={label} size={22} />
    </div>
  );
}

function DemoEntry() {
  const navigate = useNavigate();
  const { household } = useParams();
  const { search } = useLocation();
  const [error, setError] = useState<string | null>(null);
  const tour = new URLSearchParams(search).get("tour") === "1";
  const open = () => {
    setError(null);
    api.startDemo(false, household).then(
      (h) => navigate(`/h/${h.id}${tour ? "?tour=1" : ""}`, { replace: true }),
      (e) => setError(errorText(e, "Couldn't open the sample household.")),
    );
  };
  useEffect(open, [household]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="center-page">
      <Brand />
      {error ? <ErrorNote message={error} onRetry={open} /> : <Spinner label="Opening the sample household…" size={22} />}
    </div>
  );
}

function NotFound() {
  return (
    <div className="center-page">
      <Brand />
      <h1>That page isn't here.</h1>
      <Link to="/" className="btn btn-primary">
        Go to the start
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <UsageProvider>
            <TourProvider>
              <Suspense fallback={<Loading />}>
                <Routes>
                  <Route path="/" element={<Landing />} />
                  <Route path="/start" element={<Start />} />
                  <Route path="/demo" element={<DemoEntry />} />
                  <Route path="/demo/:household" element={<DemoEntry />} />
                  <Route path="/h/:hid/*" element={<HouseholdApp />} />
                  <Route path="/evals" element={<Evals />} />
                  <Route path="/handover" element={<Handover />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </TourProvider>
          </UsageProvider>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
