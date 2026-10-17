// Light / dark / system. The choice is kept on this device only (see state/app.tsx).

export type ThemeChoice = "light" | "dark" | "system";

function systemDark(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

export function resolve(choice: ThemeChoice): "light" | "dark" {
  return choice === "system" ? (systemDark() ? "dark" : "light") : choice;
}

export function apply(choice: ThemeChoice): void {
  const mode = resolve(choice);
  document.documentElement.dataset.theme = mode;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", mode === "dark" ? "#08151a" : "#eef2f3");
}

/** Call once before React renders, so the first paint is already in the right theme. */
export function applyStored(): void {
  let choice: ThemeChoice = "system";
  try {
    const v = localStorage.getItem("iid.theme");
    if (v === "light" || v === "dark" || v === "system") choice = v;
  } catch {
    /* storage unavailable */
  }
  apply(choice);
}
