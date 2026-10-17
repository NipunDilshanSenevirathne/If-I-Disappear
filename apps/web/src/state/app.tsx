import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { api, ApiError, errorText } from "../lib/api";
import { useVisibleInterval } from "../lib/hooks";
import { apply, resolve, type ThemeChoice } from "../lib/theme";
import type { AiUsage, HouseholdView } from "../lib/types";

// ---------------------------------------------------------------------- theme

interface ThemeCtx {
  choice: ThemeChoice;
  mode: "light" | "dark";
  setChoice: (c: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeCtx | null>(null);

function storedTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem("iid.theme");
    return v === "light" || v === "dark" || v === "system" ? v : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<ThemeChoice>(storedTheme);
  const [mode, setMode] = useState<"light" | "dark">(() => resolve(storedTheme()));
  useEffect(() => {
    apply(choice);
    setMode(resolve(choice));
    try {
      localStorage.setItem("iid.theme", choice);
    } catch {
      /* storage unavailable */
    }
    if (choice !== "system") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = () => {
      apply("system");
      setMode(resolve("system"));
    };
    mq?.addEventListener("change", on);
    return () => mq?.removeEventListener("change", on);
  }, [choice]);
  const value = useMemo(() => ({ choice, mode, setChoice }), [choice, mode]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside ThemeProvider");
  return ctx;
}

// ---------------------------------------------------------------------- toasts

interface Toast {
  id: number;
  text: string;
  tone: "ok" | "error";
}

const ToastContext = createContext<(text: string, tone?: "ok" | "error") => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const push = useCallback((text: string, tone: "ok" | "error" = "ok") => {
    const id = next.current++;
    setToasts((t) => [...t.slice(-2), { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 8000 : 5000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            {t.tone === "error" ? <CircleAlert size={18} aria-hidden="true" /> : <CheckCircle2 size={18} aria-hidden="true" />}
            <span>{t.text}</span>
            <button type="button" className="icon-btn" aria-label="Dismiss" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

// ---------------------------------------------------------------------- the household

interface HouseholdCtx {
  household: HouseholdView | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setHousehold: (h: HouseholdView) => void;
  /** set when the data changed behind the scenes (live update); cleared after a moment */
  pulse: number;
}

const HouseholdContext = createContext<HouseholdCtx | null>(null);

export function HouseholdProvider({ id, children }: { id: string; children: ReactNode }) {
  const [household, setHouseholdState] = useState<HouseholdView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);
  const rev = useRef<number | null>(null);

  const setHousehold = useCallback((h: HouseholdView) => {
    rev.current = h.rev;
    setHouseholdState(h);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const h = await api.household(id);
      setHousehold(h);
      setError(null);
    } catch (e) {
      setError(errorText(e, "Couldn't load this household."));
    } finally {
      setLoading(false);
    }
  }, [id, setHousehold]);

  useEffect(() => {
    setLoading(true);
    setHouseholdState(null);
    rev.current = null;
    void refresh();
  }, [refresh]);

  // live updates: a tiny "has anything changed?" call every few seconds
  useVisibleInterval(
    () => {
      if (rev.current === null) return;
      api.pulse(id).then(
        (p) => {
          if (rev.current !== null && p.rev !== rev.current) {
            void refresh().then(() => setPulse((n) => n + 1));
          }
        },
        (e) => {
          if (e instanceof ApiError && (e.status === 404 || e.status === 403)) setError(e.message);
        },
      );
    },
    6000,
    !!household,
  );

  const value = useMemo(() => ({ household, loading, error, refresh, setHousehold, pulse }), [household, loading, error, refresh, setHousehold, pulse]);
  return <HouseholdContext.Provider value={value}>{children}</HouseholdContext.Provider>;
}

export function useHousehold(): HouseholdCtx {
  const ctx = useContext(HouseholdContext);
  if (!ctx) throw new Error("useHousehold outside HouseholdProvider");
  return ctx;
}

/** For pages under the household gate: the household is loaded. */
export function useLoaded(): Omit<HouseholdCtx, "household"> & { h: HouseholdView } {
  const ctx = useHousehold();
  if (!ctx.household) throw new Error("household not loaded");
  return { ...ctx, h: ctx.household };
}

// ---------------------------------------------------------------------- the AI allowance (live)

interface UsageCtx {
  usage: AiUsage | null;
  refresh: () => void;
  updatedAt: number;
}

const UsageContext = createContext<UsageCtx>({ usage: null, refresh: () => undefined, updatedAt: 0 });

export function UsageProvider({ children }: { children: ReactNode }) {
  const [usage, setUsage] = useState<AiUsage | null>(null);
  const [updatedAt, setUpdatedAt] = useState(0);
  const refresh = useCallback(() => {
    api.usage().then(
      (u) => {
        setUsage(u);
        setUpdatedAt(Date.now());
      },
      () => undefined,
    );
  }, []);
  useEffect(refresh, [refresh]);
  useVisibleInterval(refresh, 10_000);
  const value = useMemo(() => ({ usage, refresh, updatedAt }), [usage, refresh, updatedAt]);
  return <UsageContext.Provider value={value}>{children}</UsageContext.Provider>;
}

export function useUsage(): UsageCtx {
  return useContext(UsageContext);
}
