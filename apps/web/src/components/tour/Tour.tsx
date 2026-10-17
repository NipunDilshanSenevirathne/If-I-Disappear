import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Compass, X } from "lucide-react";
import { writeLocal } from "../../lib/hooks";

export interface TourStep {
  route: string; // relative to /h/:id ("" is the overview)
  target: string; // data-tour id
  title: string;
  body: string;
}

interface TourCtx {
  start: (steps: TourStep[], base: string) => void;
  active: boolean;
}

const TourContext = createContext<TourCtx>({ start: () => undefined, active: false });

export function useTour(): TourCtx {
  return useContext(TourContext);
}

export const TOUR_SEEN = "iid.tour.seen";

export function TourProvider({ children }: { children: ReactNode }) {
  const [steps, setSteps] = useState<TourStep[] | null>(null);
  const [base, setBase] = useState("");
  const [index, setIndex] = useState(0);
  const start = useCallback((s: TourStep[], b: string) => {
    setSteps(s);
    setBase(b);
    setIndex(0);
  }, []);
  const close = useCallback(() => {
    setSteps(null);
    writeLocal(TOUR_SEEN, "1");
  }, []);
  const value = useMemo(() => ({ start, active: steps !== null }), [start, steps]);
  return (
    <TourContext.Provider value={value}>
      {children}
      {steps && <TourOverlay steps={steps} base={base} index={index} setIndex={setIndex} onClose={close} />}
    </TourContext.Provider>
  );
}

interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

function TourOverlay({ steps, base, index, setIndex, onClose }: { steps: TourStep[]; base: string; index: number; setIndex: (i: number) => void; onClose: () => void }) {
  const step = steps[index];
  const navigate = useNavigate();
  const location = useLocation();
  const [box, setBox] = useState<Box | null>(null);
  const [searching, setSearching] = useState(true);
  const card = useRef<HTMLDivElement>(null);
  const path = step.route ? `${base}/${step.route}` : base;

  // go to the page this step is about
  useEffect(() => {
    if (location.pathname !== path) navigate(path);
  }, [path, location.pathname, navigate]);

  // find the element, scroll it into view, and follow it
  useLayoutEffect(() => {
    let cancelled = false;
    let raf = 0;
    let tries = 0;
    setSearching(true);
    setBox(null);
    const measure = () => {
      const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (!el) return false;
      const r = el.getBoundingClientRect();
      setBox({ top: r.top, left: r.left, width: r.width, height: r.height });
      return true;
    };
    const find = () => {
      if (cancelled) return;
      const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        window.setTimeout(() => {
          if (!cancelled) {
            measure();
            setSearching(false);
          }
        }, 380);
        return;
      }
      if (++tries < 40) raf = window.setTimeout(find, 80) as unknown as number;
      else setSearching(false);
    };
    find();
    const follow = () => measure();
    window.addEventListener("resize", follow);
    window.addEventListener("scroll", follow, true);
    return () => {
      cancelled = true;
      window.clearTimeout(raf);
      window.removeEventListener("resize", follow);
      window.removeEventListener("scroll", follow, true);
    };
  }, [step.target, location.pathname]);

  useEffect(() => {
    card.current?.focus();
  }, [index, searching]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") setIndex(Math.min(steps.length - 1, index + 1));
      else if (e.key === "ArrowLeft") setIndex(Math.max(0, index - 1));
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [index, steps.length, setIndex, onClose]);

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const pad = 10;
  const gap = 16;
  const mobile = vw < 720;
  const cardW = Math.min(380, vw - 24);
  const cardH = card.current?.offsetHeight ?? 240;
  let pos: React.CSSProperties = { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
  if (box && !mobile) {
    const clampTop = (t: number) => Math.min(Math.max(16, t), vh - cardH - 16);
    const centredLeft = Math.min(Math.max(16, box.left + box.width / 2 - cardW / 2), vw - cardW - 16);
    if (box.top + box.height + pad + gap + cardH <= vh) pos = { left: centredLeft, top: box.top + box.height + pad + gap };
    else if (box.top - pad - gap - cardH >= 8) pos = { left: centredLeft, top: box.top - pad - gap - cardH };
    else if (box.left + box.width + pad + gap + cardW <= vw) pos = { left: box.left + box.width + pad + gap, top: clampTop(box.top) };
    else if (box.left - pad - gap - cardW >= 8) pos = { left: box.left - pad - gap - cardW, top: clampTop(box.top) };
    else pos = { right: 24, bottom: 24 };
  }
  if (mobile) pos = { left: 12, right: 12, bottom: 12 };
  const last = index === steps.length - 1;

  return createPortal(
    <div className="tour" aria-live="polite">
      <div className="tour-scrim" onClick={onClose} />
      {box && (
        <div
          className="tour-spot"
          style={{ top: box.top - pad, left: box.left - pad, width: box.width + pad * 2, height: box.height + pad * 2 }}
          aria-hidden="true"
        />
      )}
      <div className="tour-card" style={pos} ref={card} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="tour-title">
        <div className="tour-top">
          <span className="tour-step num">
            <Compass size={14} aria-hidden="true" /> {index + 1} of {steps.length}
          </span>
          <button type="button" className="icon-btn" aria-label="Close the tour" onClick={onClose}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <h2 id="tour-title">{step.title}</h2>
        <p>{step.body}</p>
        <div className="tour-dots" aria-hidden="true">
          {steps.map((_, i) => (
            <i key={i} className={i === index ? "on" : i < index ? "done" : ""} />
          ))}
        </div>
        <div className="tour-actions">
          <button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>
            Skip the tour
          </button>
          <span className="grow" />
          {index > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIndex(index - 1)}>
              <ArrowLeft size={15} aria-hidden="true" /> Back
            </button>
          )}
          <button type="button" className="btn btn-primary btn-sm" onClick={() => (last ? onClose() : setIndex(index + 1))}>
            {last ? "Start exploring" : "Next"} {!last && <ArrowRight size={15} aria-hidden="true" />}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function householdTour(leaver: string, isDemo: boolean): TourStep[] {
  return [
    {
      route: "",
      target: "hero",
      title: "Welcome to the household dashboard",
      body: `${leaver} is leaving home for a while. Everything here is worked out from what the family recorded, and it updates by itself as things change.`,
    },
    {
      route: "",
      target: "kpis",
      title: "How ready is the house?",
      body: "Each tile counts responsibilities by state: ready, blocked, needs a check, or handover not finished. The small line shows how it has moved.",
    },
    {
      route: "",
      target: "weeks",
      title: "Across the absence, week by week",
      body: "Each bar is one week of the absence. Red means something would stop on a date. Hover or tap a bar, or use the arrow keys, to see that week.",
    },
    {
      route: "",
      target: "urgent",
      title: "The most urgent problems",
      body: "Gemini reads what the family recorded. Code works out what stops, from quoted facts, and a second AI reader checks each finding.",
    },
    {
      route: "capture",
      target: "capture",
      title: "Add what you know",
      body: "Talk, take a photo of a bill, or type. Gemini pulls out facts with the exact words they came from, and nothing is used until you've checked it.",
    },
    {
      route: "found",
      target: "finding",
      title: "What we found, and why",
      body: "Each finding shows how it was worked out, what was checked and set aside, and a question you can answer right here. Answering updates everything.",
    },
    {
      route: "explore",
      target: "explore-controls",
      title: "What if…?",
      body: "What if someone else is away too, or a phone isn't there? Switch things on and see what would change. Nothing is saved.",
    },
    {
      route: "plan",
      target: "plan-budget",
      title: "A plan for the time you have",
      body: "Choose how much time you can give. You get the fewest steps that fix the most, and who does each. A step counts once you record how you know it's done.",
    },
    {
      route: "practise",
      target: "practice-start",
      title: "Practise the handover",
      body: "The person staying explains a task back, by talking (Gemini Live) or typing. Key steps must be covered, and a hint counts as help.",
    },
    {
      route: "card",
      target: "card",
      title: "The Continuity Card",
      body: "One page for the fridge: who does what, when, and where things are. Send each person their own part from Share. It never shows PINs or passwords.",
    },
    {
      route: "",
      target: "ai-allowance",
      title: "Runs on the free Gemini tier",
      body: "This live meter shows today's allowance for each Google model. When one is busy or used up, the next one answers, so the app keeps working.",
    },
    {
      route: "",
      target: isDemo ? "demo-bar" : "hero",
      title: isDemo ? "Now try it yourself" : "You're ready",
      body: isDemo
        ? "Jump a week ahead to see the plan work, try a what-if, or open another sample household. Take this tour again any time from the top bar."
        : "Add a voice note or a photo, check the facts, then come back here. Take this tour again any time from the top bar.",
    },
  ];
}
