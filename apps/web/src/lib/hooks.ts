import { useEffect, useRef, useState } from "react";

/** Run `fn` every `ms` while the page is visible (and once when it becomes visible again). */
export function useVisibleInterval(fn: () => void, ms: number, enabled = true): void {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!enabled) return;
    let timer: number | undefined;
    const tick = () => {
      if (document.visibilityState === "visible") saved.current();
    };
    const start = () => {
      window.clearInterval(timer);
      timer = window.setInterval(tick, ms);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        tick();
        start();
      } else window.clearInterval(timer);
    };
    start();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [ms, enabled]);
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(!!mq?.matches);
    mq?.addEventListener("change", on);
    return () => mq?.removeEventListener("change", on);
  }, []);
  return reduced;
}

/** A number that eases towards its target when the target changes (for live counters). */
export function useTween(target: number, ms = 600): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    if (reduced) {
      setValue(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = a + (target - a) * eased;
      setValue(v);
      if (t < 1) raf = requestAnimationFrame(step);
      else from.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, reduced]);
  return value;
}

export function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(() => !!window.matchMedia?.(query).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    const on = () => setMatch(!!mq?.matches);
    on();
    mq?.addEventListener("change", on);
    return () => mq?.removeEventListener("change", on);
  }, [query]);
  return match;
}

export function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}
