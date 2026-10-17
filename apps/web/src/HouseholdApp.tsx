import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";
import { Shell } from "./components/shell/Shell";
import { Brand } from "./components/shell/Brand";
import { ErrorNote, Spinner } from "./components/ui";
import { HouseholdProvider, useHousehold } from "./state/app";
import Overview from "./pages/Overview";

// Everything under /h/:id. Loaded on demand, so the landing page stays light.
const Capture = lazy(() => import("./pages/Capture"));
const Review = lazy(() => import("./pages/Review"));
const Findings = lazy(() => import("./pages/Findings"));
const Explore = lazy(() => import("./pages/Explore"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Plan = lazy(() => import("./pages/Plan"));
const Practice = lazy(() => import("./pages/Practice"));
const Card = lazy(() => import("./pages/Card"));
const Share = lazy(() => import("./pages/Share"));
const Settings = lazy(() => import("./pages/Settings"));
const Trace = lazy(() => import("./pages/Trace"));

function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading-page">
      <Spinner label={label} size={22} />
    </div>
  );
}

function HouseholdGate() {
  const { household, loading, error, refresh } = useHousehold();
  if (loading && !household) return <Loading label="Opening the household…" />;
  if (error && !household)
    return (
      <div className="center-page">
        <Brand />
        <ErrorNote message={error} onRetry={() => void refresh()} />
        <Link to="/" className="btn btn-ghost">
          Back to the start
        </Link>
      </div>
    );
  if (!household) return null;
  return (
    <Shell>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route index element={<Overview />} />
          <Route path="found" element={<Findings />} />
          <Route path="explore" element={<Explore />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="plan" element={<Plan />} />
          <Route path="practise" element={<Practice />} />
          <Route path="practice" element={<Navigate to="../practise" replace />} />
          <Route path="card" element={<Card />} />
          <Route path="capture" element={<Capture />} />
          <Route path="review" element={<Review />} />
          <Route path="share" element={<Share />} />
          <Route path="settings" element={<Settings />} />
          <Route path="trace" element={<Trace />} />
          <Route path="*" element={<Navigate to="." replace />} />
        </Routes>
      </Suspense>
    </Shell>
  );
}

export default function HouseholdApp() {
  const { hid = "" } = useParams();
  return (
    <HouseholdProvider id={hid}>
      <HouseholdGate />
    </HouseholdProvider>
  );
}
