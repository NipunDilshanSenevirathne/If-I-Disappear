import { useState } from "react";
import { api, errorText, waitForJob } from "../lib/api";
import type { TraceStep } from "../lib/types";
import { useLoaded, useToast, useUsage } from "./app";

/** Run the full check again (engine + AI review) and follow its steps as they happen. */
export function useAnalyze() {
  const { h, refresh } = useLoaded();
  const toast = useToast();
  const usage = useUsage();
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<TraceStep[]>([]);

  const run = async () => {
    setRunning(true);
    setSteps([]);
    try {
      const { job } = await api.analyze(h.id);
      const done = await waitForJob(job.id, (j) => setSteps(j.progress));
      setSteps(done.progress);
      if (done.status === "error") toast(done.error ?? "The check didn't finish.", "error");
      await refresh();
      usage.refresh();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setRunning(false);
    }
  };

  return { run, running, steps };
}
